from urllib.parse import urljoin, urlparse

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required

from app.auth import bp
from app import db
from app.models import User
from app.forms import RegistrationForm, LoginForm


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

@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        # パスワードはハッシュ化してから保存する（set_password が werkzeug で処理）
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("登録が完了しました。ログインしてください。")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)

@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        # ユーザーが存在しない場合と、パスワードが違う場合を同じメッセージにする。
        # どちらが誤りかを明示しないことで、ユーザー名の存在有無が第三者に漏れるのを防ぐ。
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            # 未ログイン時にアクセスしようとしたページに戻す。
            # next パラメータがない、または外部URLならボードトップへ退避する。
            # これにより、ログイン機能を悪用した外部誘導を防止する。
            next_page = request.args.get("next")
            if not next_page or not _is_safe_redirect_target(next_page):
                next_page = url_for("todo.board")
            return redirect(next_page)
        # 失敗理由を曖昧化して、ユーザー列挙のヒントを与えない。
        flash("ユーザー名またはパスワードが違います。")
    return render_template("auth/login.html", form=form)

@bp.route("/logout")
@login_required  # 未ログインでのアクセスを防ぐ（二重ログアウト等を回避）
def logout():
    logout_user()
    flash("ログアウトしました。")
    return redirect(url_for("auth.login"))
