import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # セッション/CSRFの暗号化に使用
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_key_change_me")

    # DB
    # - Render 等: DATABASE_URL（例: postgresql://... / postgres://...）
    # - 互換: DATABASE_URI
    _db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URI")
    # SQLAlchemyで psycopg(3) ドライバを使うため、PostgreSQL系URLは postgresql+psycopg:// に正規化
    if _db_url:
        if _db_url.startswith("postgres://"):
            _db_url = _db_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif _db_url.startswith("postgresql://"):
            _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url or (
        "sqlite:///" + os.path.join(basedir, "todo_app.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
