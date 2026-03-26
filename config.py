# このファイルはアプリ全体で使う設定値をまとめるファイルです。
# ============================================================
# config.py — アプリ全体の設定を一元管理するファイル
#
# セキュリティ・DB接続・パスワードルール・レート制限など、
# アプリの振る舞いを決める値をここにまとめる。
# 各モジュールはここを参照するので、変更が1箇所で済む。
# ============================================================
import os
from datetime import timedelta

# このファイル自身があるフォルダの絶対パス。SQLite のパス組み立てに使う。
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Flask アプリ全体で共有する基本設定。

    役割ごとに値を並べておくと、「どの設定が何を守っているか」を
    ひと目で追いやすくなる。
    """
    # --- セッション暗号化キー ---
    # Cookie の署名（=改ざん検知）に使う秘密鍵。環境変数から注入し、コードに直書きしない。
    # 空のまま起動すると create_app() で RuntimeError になる（安全装置）。
    SECRET_KEY = None

    # SQLAlchemy の変更追跡機能。メモリを消費するだけなので無効にする。
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Cookie セキュリティ ---
    # HttpOnly=True → JS から Cookie を読めなくする。
    # XSS（=悪意あるスクリプトをページに注入する攻撃）でセッションを盗まれるのを防ぐ。
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True

    # SameSite=Lax → 別サイトからの POST では Cookie が送られない。
    # CSRF（=ユーザーになりすまして偽リクエストを送る攻撃）を緩和する。
    # Strict だと外部リンクからの遷移でもログアウト扱いになるので Lax を選ぶ。
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # --- CSRF トークンの有効期限（秒） ---
    # CSRF トークン = 「正規のフォームから送られた」ことを証明する使い捨てコード。
    # 無期限だと古いトークンで攻撃されうるので、1時間（3600秒）に制限する。
    WTF_CSRF_TIME_LIMIT = 3600

    # --- パスワードポリシー ---
    # ここで一元管理し、フォーム（forms.py）やテンプレートから参照する。
    PASSWORD_MIN_LENGTH = 12
    # 大文字・小文字・数字を必須にして辞書攻撃（=よくある単語の総当たり）に強くする。
    # 記号は入力が面倒なので任意。フラグで要件を柔軟に調整できる。
    PASSWORD_REQUIRE_UPPER = True
    PASSWORD_REQUIRE_LOWER = True
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SYMBOL = False

    # --- 「ログイン保持」Cookie の有効期限 ---
    # Flask-Login のデフォルト（365日）は長すぎるので 30日 に明示する。
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # --- リバースプロキシ設定 ---
    # Render 等ではアプリの前に Nginx（=リバースプロキシ）がいる。
    # ProxyFix で X-Forwarded-For ヘッダーから本当のクライアント IP を取得する。
    # 0 = ProxyFix 無効（ローカル開発用）。本番では 1 に設定する。
    PROXY_FIX_TRUSTED_HOPS = 0

    # --- レート制限（ブルートフォース＝パスワード総当たり 対策） ---
    # LOGIN:    60秒間に5回失敗 → 一時ブロック
    # REGISTER: 120秒間に6回失敗 → 一時ブロック（入力ミスを考慮して緩め）
    # メモリ内管理なので再起動でリセットされるが、ポートフォリオ規模では十分。
    LOGIN_RATE_LIMIT_ATTEMPTS = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60
    REGISTER_RATE_LIMIT_ATTEMPTS = 6
    REGISTER_RATE_LIMIT_WINDOW_SECONDS = 120

    @staticmethod
    def database_uri() -> str:
        """接続先 DB を決めて URL を返す。

        環境変数 DATABASE_URL / DATABASE_URI があれば PostgreSQL、
        なければローカルの SQLite にフォールバックする。
        本番（Render = PostgreSQL）とローカル（SQLite）を同じコードで動かすための切り替え処理。
        """
        db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URI")
        if db_url:
            # Render が返す URL 形式（postgres:// や postgresql://）を
            # SQLAlchemy 2系が認識できる postgresql+psycopg:// に変換する。
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
            elif db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return db_url
        # ローカル開発用: プロジェクト直下に SQLite ファイルを作る（DBサーバー不要）。
        return "sqlite:///" + os.path.join(basedir, "todo_app.db")
