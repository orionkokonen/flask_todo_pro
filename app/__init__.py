# ============================================================
# app/__init__.py — アプリのファクトリ（組み立て工場）
#
# Flask アプリ本体と、DB・認証・CSRF保護などの拡張機能を
# ここで一括セットアップする。全体の起点になるファイル。
# ============================================================
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

# --- Flask 拡張機能のインスタンスをモジュールレベルで作る ---
# create_app() の中で init_app() して app と紐づける（Flask のお決まりパターン）。
db = SQLAlchemy()          # DB操作（SQLAlchemy ORM）
login = LoginManager()     # ログイン状態の管理
csrf = CSRFProtect()       # CSRF トークン検証
migrate = Migrate()        # DBマイグレーション（テーブル変更の履歴管理）

# 未ログインで保護ページにアクセスしたとき、ここで指定した画面にリダイレクトする。
login.login_view = "auth.login"

# --- CSP（Content Security Policy＝読み込み元の許可リスト） ---
# ブラウザに「このサイトで読んでいいリソースの出所」を教える仕組み。
# Bootstrap / アイコンフォントを static/vendor/ にローカル配信したので、
# 全て 'self'（=自分のドメインだけ）に絞れている。
# script-src に 'unsafe-inline' がないのは、インライン JS を app.js へ移行したため。
# style-src の 'unsafe-inline' は base.html のインライン style 用に残してある。
# img-src から data: を外したのは、使っていない許可を残さず読み込み先を狭めるため。
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",        # 指定がないものは自ドメインのみ許可
        "script-src 'self'",         # JS は自ドメインのみ（XSS 対策の要）
        "style-src 'self' 'unsafe-inline'",  # CSS は自ドメイン＋インライン style
        "img-src 'self'",            # 画像は自ドメイン配信のみ。data: は使っていないので許可しない。
        "font-src 'self'",           # フォントは自ドメインのみ
        "connect-src 'self'",        # fetch/XHR は自ドメインのみ
        "object-src 'none'",         # Flash 等のプラグインは全面禁止
        "base-uri 'self'",           # <base> タグの悪用を防止
        "form-action 'self'",        # フォーム送信先は自ドメインのみ
        "frame-ancestors 'none'",    # iframe での埋め込みを禁止
        "manifest-src 'self'",       # PWA マニフェストは自ドメインのみ
        "worker-src 'self'",         # Service Worker は自ドメインのみ
    ]
)


def build_content_security_policy(*, upgrade_insecure_requests: bool = False) -> str:
    if not upgrade_insecure_requests:
        return CONTENT_SECURITY_POLICY
    return "; ".join((CONTENT_SECURITY_POLICY, "upgrade-insecure-requests"))


def create_app(config_overrides: dict[str, Any] | None = None):
    """アプリ本体を組み立てるファクトリ関数。

    何をする: Flask アプリを作り、設定・拡張機能・ルートを全部セットアップして返す。
    なぜ必要: テストや本番で異なる設定を注入できるようにするため（ファクトリパターン）。
    """
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["SQLALCHEMY_DATABASE_URI"] = Config.database_uri()

    # 環境変数の SECRET_KEY があれば設定に反映する。
    secret_key = os.environ.get("SECRET_KEY")
    if secret_key:
        app.config["SECRET_KEY"] = secret_key

    # テスト等から渡された設定で上書きする。
    if config_overrides:
        app.config.update(config_overrides)

    # --- ProxyFix（リバースプロキシ対応） ---
    # Render 等では Nginx がアプリの前にいて、クライアントの本当の IP が見えない。
    # ProxyFix は X-Forwarded-For ヘッダーを読んで本来の IP を復元する。
    # hops=0（デフォルト）= 無効、hops=1 =「プロキシ1段」として有効にする。
    hops = int(app.config.get("PROXY_FIX_TRUSTED_HOPS", 0) or 0)
    if hops > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    # --- Secure Cookie の自動切替 ---
    # Secure=True → HTTPS でしか Cookie を送らない。
    # ローカル開発は HTTP なので True だとログインできなくなる。
    # → TESTING / DEBUG 時は自動で False にする。
    secure_cookies = not (app.config.get("TESTING") or app.config.get("DEBUG"))
    if not (config_overrides and "SESSION_COOKIE_SECURE" in config_overrides):
        app.config["SESSION_COOKIE_SECURE"] = secure_cookies
    if not (config_overrides and "REMEMBER_COOKIE_SECURE" in config_overrides):
        app.config["REMEMBER_COOKIE_SECURE"] = secure_cookies

    # SECRET_KEY がないと Cookie の改ざん検知ができないので、起動を止める（安全装置）。
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable must be set.")

    # --- 拡張機能をアプリに紐づける ---
    db.init_app(app)
    login.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)  # Alembic でテーブル変更を履歴管理

    # --- Blueprint（=URLグループ）を登録 ---
    from app.auth import bp as auth_bp
    from app.todo import bp as todo_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")   # /auth/login, /auth/register 等
    app.register_blueprint(todo_bp, url_prefix="/todo")    # /todo/, /todo/tasks/new 等

    # --- アプリ直下のルート ---

    @app.route("/")
    def root():
        """トップページ → ボード画面にリダイレクト。"""
        return redirect(url_for("todo.board"))

    # PWA（Progressive Web App）関連ファイルを static/ から配信する。
    # ブラウザが /sw.js 等のパスでアクセスしてくるので、static/ の中身を返す。
    # max_age=0 で常に最新版を取りに行かせる。
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

    # --- セキュリティヘッダーを全レスポンスに付与 ---
    @app.after_request
    def apply_security_headers(response):
        """全レスポンスにセキュリティヘッダーを付ける。

        何をする: ブラウザに「このサイトのセキュリティルール」を伝えるヘッダーを追加。
        なぜ必要: XSS・クリックジャッキング・中間者攻撃などをブラウザ側でも防ぐため。

        各ヘッダーの役割:
        - X-Content-Type-Options: ファイル種別の誤認を防ぐ
        - X-Frame-Options: iframe 埋め込みを禁止（クリックジャッキング対策）
        - Referrer-Policy: 外部リンク時にページ URL が漏れるのを防ぐ
        - Permissions-Policy: カメラ・マイクなどのブラウザ API を使わせない
        - CSP: 読み込み元の許可リスト（上で定義した CONTENT_SECURITY_POLICY）
        - HSTS: HTTPS を強制する宣言（本番のみ。HTTP 開発環境では出さない）
        """
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = build_content_security_policy(
            upgrade_insecure_requests=bool(app.config.get("SESSION_COOKIE_SECURE"))
        )

        # HSTS は「このサイトには今後も HTTPS で来て」とブラウザに覚えさせる仕組み。
        # 開発中の HTTP 環境で出すと動作確認しづらくなるので、本番相当の時だけ付ける。
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    return app
