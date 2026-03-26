# このファイルは Alembic がアプリのモデルを読み込むための設定ファイルです。
# migrations/env.py — Alembic（DBマイグレーション）の実行環境設定。
# flask db upgrade / flask db migrate 時に自動で読み込まれる。
import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

config = context.config

# マイグレーション実行ログをアプリと同じ粒度で出力する。
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    """Flask-SQLAlchemy のバージョン差を吸収して DB エンジンを取得する。"""
    try:
        return current_app.extensions['migrate'].db.get_engine()  # v2 以前
    except (TypeError, AttributeError):
        return current_app.extensions['migrate'].db.engine  # v3 以降


def get_engine_url():
    """Alembic が使う DB 接続文字列を取り出す。

    `%` を `%%` に置き換えているのは、Alembic の設定パーサが
    `%` を特別な記号として読むため。そのままだと URL 解釈で崩れることがある。
    """
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# DB URL は固定文字列ではなく Flask アプリの設定から取得する。
# これにより、Render(Postgres)とローカル(SQLite)の差分を env var だけで吸収できる。
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

def get_metadata():
    """マイグレーション比較に使う SQLAlchemy のメタデータを返す。

    メタデータは「どんなテーブルや列があるか」という設計図。
    ここを Alembic に渡すことで、モデルと DB の差分を自動比較できる。
    """
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """オフラインモードでマイグレーションを実行する。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """オンラインモードでマイグレーションを実行する。"""

    # autogenerate 時に差分がない場合はリビジョンファイルを作らない。
    # 「空マイグレーション」の蓄積を防ぎ、履歴の可読性を維持する。
    def process_revision_directives(context, revision, directives):
        """差分が空なら新しい migration ファイルを作らない。

        何も変わっていないのに空ファイルだけ増えると、
        後から履歴を読む人が「本当に必要な変更」を見つけにくくなる。
        """
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
