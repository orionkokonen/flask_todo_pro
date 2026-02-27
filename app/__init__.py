from __future__ import annotations

import os
from typing import Any

from flask import Flask, redirect, send_from_directory, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import Config


db = SQLAlchemy()
login = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

login.login_view = "auth.login"


def create_app(config_overrides: dict[str, Any] | None = None):
    """アプリ本体を組み立てるファクトリ関数。

    依存（DB/認証/CSRF/マイグレーション）をここで一元初期化し、
    実行環境ごとの差分は設定値だけで吸収する。
    """
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["SQLALCHEMY_DATABASE_URI"] = Config.database_uri()

    secret_key = os.environ.get("SECRET_KEY")
    if secret_key:
        app.config["SECRET_KEY"] = secret_key

    if config_overrides:
        app.config.update(config_overrides)

    # セッション改ざん対策の鍵が無い状態で起動しないための安全装置。
    # 「動くこと」より「安全に動くこと」を優先して明示的に失敗させる。
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable must be set.")

    # 拡張機能はここで app に紐づける。migrate を有効にすることで、
    # 起動時 create_all ではなく Alembic の履歴管理に統一できる。
    db.init_app(app)
    login.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    from app.auth import bp as auth_bp
    from app.todo import bp as todo_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(todo_bp, url_prefix="/todo")

    @app.route("/")
    def root():
        return redirect(url_for("todo.board"))

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
