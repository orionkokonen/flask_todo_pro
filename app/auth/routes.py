# ============================================================
# auth/routes.py — 本人確認（ログイン・登録・ログアウト）のルート定義
#
# ユーザーがアカウントを作成し、本人確認を経てサービスを利用するための
# 画面と処理をまとめたファイル。
# ============================================================
from urllib.parse import urljoin, urlparse

from flask import current_app, flash, make_response, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app import db
from app.auth import bp
from app.forms import LoginForm, RegistrationForm
from app.models import User
from app.security import auth_rate_limiter


def _is_safe_redirect_target(target: str) -> bool:
    """リダイレクト先が自分のサイト内かチェックする。

    Open Redirect（＝悪意ある外部URLへユーザーを飛ばす攻撃）を防ぐための関数。
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def _client_ip() -> str:
    """アクセス元の IP アドレスを返す。

    レート制限は「誰から来た試行か」を区別したいので、ここで IP を使う。
    本番で ProxyFix を有効にしていれば、プロキシの向こう側にいる元の利用者の IP が入る。
    """
    return request.remote_addr or "unknown"


def _render_auth_template(
    template_name: str,
    form,
    *,
    status_code: int = 200,
    retry_after: int | None = None,
):
    """ログイン・登録ページの HTML を返す共通処理。

    画面を返す流れを 1 か所にまとめておくと、
    ステータスコードや Retry-After の付け忘れを防ぎやすい。
    """
    context = {"form": form}
    if template_name == "auth/register.html":
        context["password_min_length"] = current_app.config["PASSWORD_MIN_LENGTH"]

    response = make_response(render_template(template_name, **context), status_code)
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def _rate_limited_response(template_name: str, form, retry_after: int):
    """短時間に何度もリクエストが来たとき、429（Too Many Requests）エラーを返す。

    HTTPステータス429＝「リクエストが多すぎる」ことを示す標準のエラーコード。
    """
    flash(
        "試行回数が多すぎます。"
        "少し時間を置いて再試行してください。",
        "warning",
    )
    return _render_auth_template(
        template_name,
        form,
        status_code=429,
        retry_after=retry_after,
    )


@bp.route("/register", methods=["GET", "POST"])
def register():
    """ユーザー登録ページ。新しいアカウントを作成する。"""
    form = RegistrationForm()
    bucket = f"register:{_client_ip()}"

    if request.method == "POST":
        # フォーム検証より先にレート制限をチェックし、大量リクエストからサーバーを守る。
        allowed, retry_after = auth_rate_limiter.check(
            bucket,
            current_app.config["REGISTER_RATE_LIMIT_ATTEMPTS"],
            current_app.config["REGISTER_RATE_LIMIT_WINDOW_SECONDS"],
        )
        if not allowed:
            return _rate_limited_response("auth/register.html", form, retry_after)

    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        # 成功したら同じ IP の失敗カウントを消し、正規ユーザーを巻き込まないようにする。
        auth_rate_limiter.reset(bucket)
        # 登録直後に自動ログインし、再入力の手間を省く。
        login_user(user)
        flash("登録が完了しました。ログインしました。")
        # 登録後は固定ページへ飛ばす。next パラメータを使わないのは Open Redirect 対策。
        return redirect(url_for("todo.board"))

    if request.method == "POST":
        # 入力ミスの連打も短時間に大量なら負荷になるため、失敗として数える。
        auth_rate_limiter.record_failure(
            bucket,
            current_app.config["REGISTER_RATE_LIMIT_WINDOW_SECONDS"],
        )
    return _render_auth_template("auth/register.html", form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """ログインページ。ユーザー名とパスワードで本人確認する。"""
    form = LoginForm()
    bucket = f"login:{_client_ip()}"

    if request.method == "POST":
        # パスワード総当たり（ブルートフォース）攻撃を防ぐためのレート制限
        allowed, retry_after = auth_rate_limiter.check(
            bucket,
            current_app.config["LOGIN_RATE_LIMIT_ATTEMPTS"],
            current_app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"],
        )
        if not allowed:
            return _rate_limited_response("auth/login.html", form, retry_after)

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            # 成功した時点で失敗回数を消し、次回ログイン時に影響が残らないようにする。
            auth_rate_limiter.reset(bucket)
            login_user(user, remember=form.remember_me.data)
            # 監査ログ: 後で「いつ誰が入れたか」を追えるように残す。
            current_app.logger.info(
                "login succeeded: user_id=%s username=%s ip=%s",
                user.id,
                user.username,
                _client_ip(),
            )
            # ログイン前に行こうとしたページへ戻す。安全な URL か必ず検証する。
            next_page = request.args.get("next")
            if not next_page or not _is_safe_redirect_target(next_page):
                next_page = url_for("todo.board")
            return redirect(next_page)

        # 失敗を記録して、短時間の連続試行をブロックできるようにする。
        auth_rate_limiter.record_failure(
            bucket,
            current_app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"],
        )
        # 監査ログ: 不自然な失敗連打があった時の手がかりにする。
        current_app.logger.warning(
            "login failed: username=%s ip=%s",
            form.username.data,
            _client_ip(),
        )
        # ユーザー名・パスワードのどちらが間違っているかは教えない（セキュリティ上の配慮）。
        flash("ユーザー名またはパスワードが違います。")
    return _render_auth_template("auth/login.html", form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """ログアウト処理。POST のみ受け付けるのは CSRF 対策のため。"""
    # セッション（＝ログイン状態の記録）を消して、本人確認済み状態を終わらせる。
    logout_user()
    flash("ログアウトしました。")
    return redirect(url_for("auth.login"))
