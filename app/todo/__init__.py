from flask import Blueprint

# Blueprint（ルーティングのグループ）を定義し、後からルートをインポートする。
# routes_* を先頭でインポートすると bp がまだ未定義で循環インポートになるため、
# bp 定義の後にインポートするのが Flask Blueprint の慣例パターン。
# 責務ごとにファイルを分割（board/tasks/projects/teams）し、1 ファイルの肥大化を防いでいる。
bp = Blueprint("todo", __name__, template_folder="templates")

from app.todo import routes_board, routes_projects, routes_tasks, routes_teams  # noqa: E402,F401
