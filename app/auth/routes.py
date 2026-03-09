# ============================================================
# auth/routes.py — 本人確認（ログイン・登録・ログアウト）のルート定義
#
# ユーザーがアカウントを作成し、本人確認を経てサービスを利用するための
# 画面と処理をまとめたファイル。
# ============================================================
from urllib.parse import urljoin, urlparse

from flask import current_app, flash, make_response, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.auth import bp
from app.db_utils import rollback_session
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

    HTTPステータス429 は「短時間に来すぎたので少し待って」という意味。
    エラー画面ではなく通常のフォーム画面を返しつつ、待ち時間の目安もヘッダーへ載せる。
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
    """ユーザー登録ページ。

    入力チェック、レート制限、保存失敗時の後片づけまでを 1 つの流れとして扱う。
    """
    form = RegistrationForm()
    # bucket は「この IP の登録試行回数」を数えるための名前。
    # 文字列の中身は自由だが、用途ごとに分けると login と register を別々に数えられる。
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
        try:
            db.session.add(user)
            # commit() はここまで積んだ変更を本当に DB へ確定する場所。
            # 失敗しやすい境目なので、try/except で囲って後片づけを明示する。
            db.session.commit()
        except SQLAlchemyError:
            rollback_session("user registration")
            # 画面には原因を細かく出さず、入力見直しを促す文言だけ返す。
            # 詳細は rollback_session() 側のログへ残す。
            flash("登録を完了できませんでした。入力内容を確認して再試行してください。", "danger")
            return _render_auth_template("auth/register.html", form)
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
    """ログインページ。

    「その人本人か」を確認する入口で、成功時はセッションを作り、
    失敗時は回数を記録して総当たり攻撃を遅くする。
    """
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
        # まずユーザー名で探し、見つかったときだけパスワード照合へ進む。
        # ただし画面には「どちらが違ったか」は出さず、推測材料を増やさない。
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
        # 「ユーザー名がない」「パスワードだけ違う」を出し分けると、
        # 攻撃者に登録済みアカウントを推測されやすくなるので文言はまとめる。
        flash("ログインに失敗しました。入力内容を確認してください。")
    return _render_auth_template("auth/login.html", form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """ログアウト処理。POST のみ受け付けるのは CSRF 対策のため。"""
    # セッション（＝ログイン状態の記録）を消して、本人確認済み状態を終わらせる。
    logout_user()
    flash("ログアウトしました。")
    return redirect(url_for("auth.login"))
