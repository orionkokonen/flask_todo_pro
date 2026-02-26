import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # SECRET_KEY is required at runtime and injected via environment.
    SECRET_KEY = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def database_uri() -> str:
        db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URI")
        if db_url:
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
            elif db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return db_url
        return "sqlite:///" + os.path.join(basedir, "todo_app.db")
