import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # SECRET_KEY はセッション・CSRF トークンの署名に使われる。
    # 本番環境では必ず環境変数で上書きし、デフォルト値のまま運用しない。
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_key_change_me")

    # DB 接続先を環境変数から取得する。
    # Render の Postgres サービスは DATABASE_URL を自動で注入するが、
    # 古い形式 "postgres://" で渡されることがある。
    # SQLAlchemy (psycopg3 ドライバ) は "postgresql+psycopg://" を要求するため、
    # ここでプレフィックスを正規化して互換性を保つ。
    _db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URI")
    if _db_url:
        if _db_url.startswith("postgres://"):
            _db_url = _db_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif _db_url.startswith("postgresql://"):
            _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    # 環境変数が未設定のローカル開発時は SQLite にフォールバックする。
    # これにより Postgres がなくても即座に動作確認できる。
    SQLALCHEMY_DATABASE_URI = _db_url or (
        "sqlite:///" + os.path.join(basedir, "todo_app.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
