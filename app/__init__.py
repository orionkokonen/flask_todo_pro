from __future__ import annotations

import os
from typing import Any

from flask import Flask, redirect, send_from_directory, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config


db = SQLAlchemy()
login = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

login.login_view = "auth.login"

# CDN（Bootstrap / Bootstrap Icons）を許可しつつ、外部からのスクリプト埋め込みを制限する CSP。
# onsubmit 等の inline event handler を app.js の data-confirm パターンに移行したことで、
# script-src から 'unsafe-inline' を外せるようになり、XSS 経由の任意スクリプト実行リスクを低減した。
# style-src には 'unsafe-inline' を残しているが、これは Bootstrap のカスタムスタイル互換のため。
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://cdn.jsdelivr.net",
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' https://cdn.jsdelivr.net",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "manifest-src 'self'",
        "worker-src 'self'",
    ]
)


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

    # PROXY_FIX_TRUSTED_HOPS が 1 以上のときだけ ProxyFix を WSGI ミドルウェアとして導入する。
    # ProxyFix は X-Forwarded-For などのヘッダーを解釈して remote_addr を実クライアント IP に書き換える。
    # hops=0 のデフォルトでは無効のままにし、ローカル公開や直接公開での IP 偽装を避ける。
    # 単一の信頼できるリバースプロキシ配下では hops=1 を想定するが、実際の hop 数に合わせて調整する。
    hops = int(app.config.get("PROXY_FIX_TRUSTED_HOPS", 0) or 0)
    if hops > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    # Secure 属性は HTTPS 環境でのみ意味を持つ。ローカル HTTP 開発で True にすると
    # ブラウザが Cookie を送らずログインできなくなるため、TESTING / DEBUG 時は False にする。
    # config_overrides で明示指定された場合は上書きせずその値を優先する。
    secure_cookies = not (app.config.get("TESTING") or app.config.get("DEBUG"))
    if not (config_overrides and "SESSION_COOKIE_SECURE" in config_overrides):
        app.config["SESSION_COOKIE_SECURE"] = secure_cookies
    if not (config_overrides and "REMEMBER_COOKIE_SECURE" in config_overrides):
        app.config["REMEMBER_COOKIE_SECURE"] = secure_cookies

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

    @app.after_request
    def apply_security_headers(response):
        """全レスポンスにブラウザ側のセキュリティヘッダーを付与する。

        アプリケーション層で設定することで、Nginx / CDN の有無に関わらず
        一貫したヘッダーを保証できる。各ヘッダーの役割は以下の通り。
        - X-Content-Type-Options: MIME スニッフィングを防ぎ XSS リスクを低減する。
        - X-Frame-Options: クリックジャッキング攻撃（iframe 埋め込み）をブロックする。
        - Referrer-Policy: 外部サイトへのリンク時にリファラーで内部 URL が漏れるのを防ぐ。
        - Permissions-Policy: カメラ・マイク・位置情報へのブラウザ API アクセスを封じる。
        - CSP: スクリプト・スタイルの読み込み元をホワイトリストで制限する。
        - HSTS: HTTPS 強制を宣言し、HTTP へのダウングレード攻撃（SSL ストリッピング）を防ぐ。
          Secure cookie が有効な本番環境でのみ付与し、HTTP 開発環境では出力しない。
        """
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY

        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    return app
