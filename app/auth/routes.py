from urllib.parse import urljoin, urlparse

from flask import current_app, flash, make_response, redirect, render_template, request, url_for
from flask_login import login_user, logout_user, login_required

from app.auth import bp
from app import db
from app.models import User
from app.forms import RegistrationForm, LoginForm
from app.security import auth_rate_limiter


def _is_safe_redirect_target(target: str) -> bool:
    """ログイン後遷移先が同一オリジンかを検証する。

    外部URLへのリダイレクトを防ぎ、Open Redirect 脆弱性を回避する。
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (
        test_url.scheme in ("http", "https")
        and ref_url.netloc == test_url.netloc
    )


def _client_ip() -> str:
    if request.access_route:
        return request.access_route[0]
    return request.remote_addr or "unknown"


def _render_auth_template(
    template_name: str,
    form,
    *,
    status_code: int = 200,
    retry_after: int | None = None,
):
    context = {"form": form}
    if template_name == "auth/register.html":
        context["password_min_length"] = current_app.config["PASSWORD_MIN_LENGTH"]

    response = make_response(render_template(template_name, **context), status_code)
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def _rate_limited_response(template_name: str, form, retry_after: int):
    flash("試行回数が多すぎます。少し時間を置いて再試行してください。", "warning")
    return _render_auth_template(
        template_name,
        form,
        status_code=429,
        retry_after=retry_after,
    )

@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    bucket = f"register:{_client_ip()}"

    if request.method == "POST":
        allowed, retry_after = auth_rate_limiter.check(
            bucket,
            current_app.config["REGISTER_RATE_LIMIT_ATTEMPTS"],
            current_app.config["REGISTER_RATE_LIMIT_WINDOW_SECONDS"],
        )
        if not allowed:
            return _rate_limited_response("auth/register.html", form, retry_after)

    if form.validate_on_submit():
        user = User(username=form.username.data)
        # パスワードはハッシュ化してから保存する（set_password が werkzeug で処理）
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        auth_rate_limiter.reset(bucket)
        flash("登録が完了しました。ログインしてください。")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        auth_rate_limiter.record_failure(
            bucket,
            current_app.config["REGISTER_RATE_LIMIT_WINDOW_SECONDS"],
        )
    return _render_auth_template("auth/register.html", form)

@bp.route("/login", methods=["GET", "POST"])
def login():
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
        # ユーザーが存在しない場合と、パスワードが違う場合を同じメッセージにする。
        # どちらが誤りかを明示しないことで、ユーザー名の存在有無が第三者に漏れるのを防ぐ。
        if user and user.check_password(form.password.data):
            auth_rate_limiter.reset(bucket)
            login_user(user, remember=form.remember_me.data)
            # 未ログイン時にアクセスしようとしたページに戻す。
            # next パラメータがない、または外部URLならボードトップへ退避する。
            # これにより、ログイン機能を悪用した外部誘導を防止する。
            next_page = request.args.get("next")
            if not next_page or not _is_safe_redirect_target(next_page):
                next_page = url_for("todo.board")
            return redirect(next_page)
        # 失敗理由を曖昧化して、ユーザー列挙のヒントを与えない。
        auth_rate_limiter.record_failure(
            bucket,
            current_app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"],
        )
        flash("ユーザー名またはパスワードが違います。")
    return _render_auth_template("auth/login.html", form)

@bp.route("/logout")
@login_required  # 未ログインでのアクセスを防ぐ（二重ログアウト等を回避）
def logout():
    logout_user()
    flash("ログアウトしました。")
    return redirect(url_for("auth.login"))
