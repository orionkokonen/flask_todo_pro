import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # SECRET_KEY は起動時に必須で、環境変数から注入する。設定ファイルに直書きしてはならない。
    SECRET_KEY = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # HttpOnly: JS から Cookie を読めなくする。
    # → XSS（ページに悪意あるスクリプトを注入する攻撃）でセッションを盗まれるのを防ぐ。
    # REMEMBER は「ログイン保持」チェック用の永続 Cookie。
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True

    # SameSite=Lax: 別サイトからの POST で Cookie が送られない。
    # → CSRF（ユーザーになりすまして偽リクエストを送る攻撃）を緩和する。
    # Strict だと外部リンクからの遷移でログアウト扱いになるため Lax を選択。
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # CSRF トークン（正規のフォーム送信か検証する使い捨てコード）の有効期限（秒）。
    # 無制限だと古いトークンで攻撃が成立しうるため 1 時間に制限。
    WTF_CSRF_TIME_LIMIT = 3600

    # パスワードの最低文字数。ここで一元管理し、フォームやテンプレートから参照する。
    PASSWORD_MIN_LENGTH = 12
    # 大文字・小文字・数字を必須にして辞書攻撃（よくある単語の総当たり）への耐性を高める。
    # 記号は UX の障壁が大きいため任意。フラグ切替で要件を柔軟に調整できる。
    PASSWORD_REQUIRE_UPPER = True
    PASSWORD_REQUIRE_LOWER = True
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SYMBOL = False

    # 「ログイン保持」チェック時の Cookie 有効期限。
    # Flask-Login デフォルト（365 日）は長すぎるため 30 日に明示する。
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # リバースプロキシ（Render では Nginx 等）を経由する段数。0 で ProxyFix 無効。
    # X-Forwarded-For（接続元 IP を伝えるヘッダー）を無条件に信頼すると
    # IP 偽装が可能になるため、本番のプロキシ構成に合わせて設定する。
    PROXY_FIX_TRUSTED_HOPS = 0

    # ブルートフォース（パスワード総当たり）対策のレート制限。
    # LOGIN: 60 秒に 5 回失敗でブロック。REGISTER: 120 秒に 6 回（入力ミスを考慮し緩め）。
    # メモリ内管理のため再起動でリセットされるが、ポートフォリオ規模では十分。
    LOGIN_RATE_LIMIT_ATTEMPTS = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60
    REGISTER_RATE_LIMIT_ATTEMPTS = 6
    REGISTER_RATE_LIMIT_WINDOW_SECONDS = 120

    @staticmethod
    def database_uri() -> str:
        """実行環境に応じて接続先DBを決定する。

        本番(Render)は環境変数を優先し、ローカルではSQLiteへフォールバックすることで、
        セットアップ手順を最小化しつつ本番互換の構成を保つ。
        """
        db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URI")
        if db_url:
            # Render が返す URL 形式（postgres:// や postgresql://）を
            # SQLAlchemy 2 系が認識できる postgresql+psycopg:// に変換する。
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
            elif db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return db_url
        # ローカル開発はDBサーバー不要で再現できるよう、プロジェクト配下SQLiteを使う。
        return "sqlite:///" + os.path.join(basedir, "todo_app.db")
