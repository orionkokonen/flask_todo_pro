import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # SECRET_KEY is required at runtime and injected via environment.
    SECRET_KEY = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
