from urllib.parse import urljoin, urlparse

from flask import current_app, flash, make_response, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app import db
from app.auth import bp
from app.forms import LoginForm, RegistrationForm
from app.models import User
from app.security import auth_rate_limiter


def _is_safe_redirect_target(target: str) -> bool:
    """リダイレクト先が同一ホストの URL かどうかを検証する。外部 URL への誘導（Open Redirect）を防ぐ。"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def _client_ip() -> str:
    """Flask から見えるクライアント IP を返す。ProxyFix が有効な場合は X-Forwarded-For 解釈後の値になる。"""
    return request.remote_addr or "unknown"


def _render_auth_template(
    template_name: str,
    form,
    *,
    status_code: int = 200,
    retry_after: int | None = None,
):
    """認証テンプレートを描画し、必要に応じて Retry-After ヘッダーを付けてレスポンスを返す。"""
    context = {"form": form}
    if template_name == "auth/register.html":
        context["password_min_length"] = current_app.config["PASSWORD_MIN_LENGTH"]

    response = make_response(render_template(template_name, **context), status_code)
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def _rate_limited_response(template_name: str, form, retry_after: int):
    """レート制限超過時にユーザーへ警告を表示し 429 レスポンスを返す。

    Retry-After ヘッダーを付与することで、クライアント（自動リトライツール等）に
    次に試せるまでの待機時間を通知する HTTP 標準の仕組み。
    """
    flash(
        "\u8a66\u884c\u56de\u6570\u304c\u591a\u3059\u304e\u307e\u3059\u3002"
        "\u5c11\u3057\u6642\u9593\u3092\u7f6e\u3044\u3066\u518d\u8a66\u884c\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
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
    """登録画面を表示し、フォーム送信時にユーザーアカウントを作成する。"""
    form = RegistrationForm()
    bucket = f"register:{_client_ip()}"

    if request.method == "POST":
        # validate_on_submit() より先に IP ごとの試行回数を確認する。
        # バリデーション処理を実行する前にブロックすることで、
        # 大量リクエストによるサーバー負荷も同時に抑制できる。
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
        auth_rate_limiter.reset(bucket)
        # 登録完了直後にそのままログイン状態にする。
        # ユーザーが「登録 → ログイン」と 2 回操作する手間を省き、登録直後の離脱を防ぐ UX 設計。
        login_user(user)
        flash(
            "\u767b\u9332\u304c\u5b8c\u4e86\u3057\u307e\u3057\u305f\u3002"
            "\u30ed\u30b0\u30a4\u30f3\u3057\u307e\u3057\u305f\u3002"
        )
        # 登録後は常にボードトップへ遷移する。
        # next パラメータを受け付けないことで、外部 URL への誘導（Open Redirect 攻撃）を防ぐ。
        return redirect(url_for("todo.board"))

    if request.method == "POST":
        auth_rate_limiter.record_failure(
            bucket,
            current_app.config["REGISTER_RATE_LIMIT_WINDOW_SECONDS"],
        )
    return _render_auth_template("auth/register.html", form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """ログイン画面を表示し、フォーム送信時にユーザーを認証する。"""
    form = LoginForm()
    bucket = f"login:{_client_ip()}"

    if request.method == "POST":
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
            auth_rate_limiter.reset(bucket)
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get("next")
            if not next_page or not _is_safe_redirect_target(next_page):
                next_page = url_for("todo.board")
            return redirect(next_page)

        auth_rate_limiter.record_failure(
            bucket,
            current_app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"],
        )
        flash(
            "\u30e6\u30fc\u30b6\u30fc\u540d\u307e\u305f\u306f"
            "\u30d1\u30b9\u30ef\u30fc\u30c9\u304c\u9055\u3044\u307e\u3059\u3002"
        )
    return _render_auth_template("auth/login.html", form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """現在のユーザーをログアウトし、ログイン画面へリダイレクトする。"""
    logout_user()
    flash("\u30ed\u30b0\u30a2\u30a6\u30c8\u3057\u307e\u3057\u305f\u3002")
    return redirect(url_for("auth.login"))
