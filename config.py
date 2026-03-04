import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # SECRET_KEY は起動時に必須で、環境変数から注入する。設定ファイルに直書きしてはならない。
    SECRET_KEY = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # HttpOnly=True により JavaScript から Cookie を読み取れなくし、
    # XSS 攻撃によるセッションハイジャックを防ぐ。
    # SESSION は通常セッション、REMEMBER は「ログイン状態を保持する」チェック時に使われる永続 Cookie。
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True

    # SameSite=Lax により、クロスサイトのフォーム送信に Cookie が乗らなくなる。
    # Flask-WTF の CSRF トークン検証と組み合わせた二重の CSRF 対策。
    # Strict ではなく Lax にするのは、外部リンクから遷移してきたユーザーが
    # ログイン済みと認識されなくなる UX 問題を避けるため。
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # CSRF トークンの有効期限（秒）。デフォルト None（無制限）のままにしておくと、
    # 長時間開きっぱなしのタブからでも古いトークンで攻撃が成立しうるため、1 時間に制限する。
    WTF_CSRF_TIME_LIMIT = 3600

    # パスワードの最低文字数。フォームバリデーター・テンプレートはこの値を参照し、
    # コード各所にハードコードされた数字が散在するのを防ぐ。
    PASSWORD_MIN_LENGTH = 12
    # 大文字・小文字・数字を必須にすることで、辞書攻撃に対する耐性を高める。
    # 記号（SYMBOL）は UX 上の障壁が大きいため今回は任意（False）にしている。
    # これらのフラグを False にすれば要件を緩めることができ、テスト環境での調整も容易。
    PASSWORD_REQUIRE_UPPER = True
    PASSWORD_REQUIRE_LOWER = True
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SYMBOL = False

    # remember_me チェック時に発行される永続 Cookie の有効期限。
    # デフォルト任せ（Flask-Login の 365 日）にするとセッション管理が不透明になるため、
    # 30 日に明示して意図を設定に残す。
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # リバースプロキシを信頼できる hop 数。0 のときは ProxyFix を無効にする。
    # X-Forwarded-For を無条件に信頼すると IP 偽装の余地があるため、通常は 0 のままにする。
    # 単一の信頼できるリバースプロキシ配下では 1 を想定する。
    # ただし hop 数は実際の配備構成に合わせて調整する。
    PROXY_FIX_TRUSTED_HOPS = 0

    # 認証エンドポイントへのブルートフォース対策のパラメータ。
    # LOGIN は短時間の連続失敗を強めに抑え、REGISTER は通常の入力ミスを考慮して少し緩めにする。
    # in-memory 実装のためプロセス間は共有されないが、シングルプロセスのポートフォリオ環境には十分。
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
            # Render等で使われる旧スキーム(postgres://)を、SQLAlchemy 2系 + psycopg
            # が期待する方言名へ正規化して接続エラーを回避する。
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
            elif db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return db_url
        # ローカル開発はDBサーバー不要で再現できるよう、プロジェクト配下SQLiteを使う。
        return "sqlite:///" + os.path.join(basedir, "todo_app.db")
