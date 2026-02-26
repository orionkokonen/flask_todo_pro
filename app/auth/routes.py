from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required

from app.auth import bp
from app import db
from app.models import User
from app.forms import RegistrationForm, LoginForm

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
            # next パラメータがない場合はボードトップへ。
            next_page = request.args.get("next") or url_for("todo.board")
            return redirect(next_page)
        flash("ユーザー名またはパスワードが違います。")
    return render_template("auth/login.html", form=form)

@bp.route("/logout")
@login_required  # 未ログインでのアクセスを防ぐ（二重ログアウト等を回避）
def logout():
    logout_user()
    flash("ログアウトしました。")
    return redirect(url_for("auth.login"))
