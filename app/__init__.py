from flask import Flask, redirect, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import Config


db = SQLAlchemy()
login = LoginManager()
csrf = CSRFProtect()

# 未ログインで @login_required に入った時の遷移先
login.login_view = "auth.login"


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login.init_app(app)
    csrf.init_app(app)

    # Blueprint登録
    from app.auth import bp as auth_bp
    from app.todo import bp as todo_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(todo_bp, url_prefix="/todo")

    # DB初期化（簡易版：初回起動でテーブル作成）
    with app.app_context():
        db.create_all()

    # ルートはToDoへ（未ログインなら login_view によってログインへ）
    @app.route("/")
    def root():
        return redirect(url_for("todo.board"))

    # --- PWA endpoints ---
    # Service Worker はルートで配信しないと scope が狭くなります。
    @app.route("/sw.js")
    def pwa_service_worker():
        return send_from_directory(
            app.static_folder,
            "sw.js",
            mimetype="application/javascript",
            max_age=0,
        )

    @app.route("/manifest.webmanifest")
    def pwa_manifest():
        return send_from_directory(
            app.static_folder,
            "manifest.webmanifest",
            mimetype="application/manifest+json",
            max_age=0,
        )

    @app.route("/offline.html")
    def pwa_offline():
        return send_from_directory(
            app.static_folder,
            "offline.html",
            mimetype="text/html",
            max_age=0,
        )

    return app
