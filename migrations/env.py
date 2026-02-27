import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# Alembic 実行時に読み込まれる設定オブジェクト。
# ここから ini の値や CLI 引数へアクセスする。
config = context.config

# マイグレーションの実行ログをアプリと同じ粒度で追えるようにする。
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # 旧API互換: Flask-SQLAlchemy<3
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # 現行API: Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
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

    # autogenerate時に差分がない場合はリビジョンファイルを作らない。
    # 「空マイグレーション」の蓄積を防ぎ、履歴の可読性を維持する。
    def process_revision_directives(context, revision, directives):
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
