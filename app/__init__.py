from flask import Flask, redirect, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import Config


# 拡張機能はグローバルに宣言し、アプリへの紐付けは create_app() 内で行う。
# これにより、テストや複数アプリインスタンスの共存（Application Factory パターン）が可能になる。
db = SQLAlchemy()
login = LoginManager()
csrf = CSRFProtect()

# 未ログインで @login_required にアクセスした際のリダイレクト先
login.login_view = "auth.login"


def create_app():
    """Flask アプリケーションを生成・設定して返す（Application Factory）。

    テスト時に設定を差し替えられるよう、アプリを関数内で生成するパターンを採用。
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # 拡張機能をアプリに紐付ける
    db.init_app(app)
    login.init_app(app)
    csrf.init_app(app)  # 全フォームに CSRF 保護を自動適用する

    # 機能ごとに Blueprint で分割し、関心の分離と URL 管理の明確化を図る
    from app.auth import bp as auth_bp
    from app.todo import bp as todo_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(todo_bp, url_prefix="/todo")

    # アプリコンテキスト内で db.create_all() を呼び、未作成のテーブルを初期化する。
    # 本番では Alembic 等のマイグレーションツールが望ましいが、
    # ポートフォリオ・小規模運用では初回起動で自動作成するこの方式でも十分機能する。
    with app.app_context():
        db.create_all()

    # ルートへのアクセスはボード画面へ転送する（未ログインなら login_view が割り込む）
    @app.route("/")
    def root():
        return redirect(url_for("todo.board"))

    # --- PWA エンドポイント ---
    # Service Worker はスコープが「配信 URL 以下」になるため、
    # サブディレクトリではなくルートから配信しないと全画面をキャッシュできない。
    @app.route("/sw.js")
    def pwa_service_worker():
        return send_from_directory(
            app.static_folder,
            "sw.js",
            mimetype="application/javascript",
            max_age=0,  # SW 自体はブラウザにキャッシュさせず、常に最新を取得させる
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
