## このファイルは、新しいデータベース変更履歴ファイルを作るためのひな形です。
"""このファイルは、新しいデータベース変更ファイルを自動生成するときのひな形です。

${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

このファイル自体はテンプレート。
`flask db migrate` 実行時に `${...}` の部分が実際の値へ置き換えられて、
新しいマイグレーションファイルが生成される。
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Alembic が「どの変更がどれにつながるか」を追跡する識別情報。
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    # DB スキーマを「新しい状態」へ進める処理がここに入る。
    ${upgrades if upgrades else "pass"}


def downgrade():
    # `upgrade()` で加えた変更を巻き戻す処理がここに入る。
    ${downgrades if downgrades else "pass"}
