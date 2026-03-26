"""ToDo 機能用 Blueprint パッケージ。

ボード、タスク、プロジェクト、チームを 1 つの大きな機能群としてまとめ、
URL のまとまりを auth 側と分けて見通しをよくしている。
"""
from flask import Blueprint

# Blueprint（URL ルーティングをグループ化する Flask の仕組み）を定義。
# bp 定義より前に routes_* をインポートすると bp が未定義で循環エラーになるため、
# 定義後にインポートする。責務ごとにファイル分割して 1 ファイルの肥大化を防いでいる。
bp = Blueprint("todo", __name__, template_folder="templates")

from app.todo import routes_board, routes_projects, routes_tasks, routes_teams  # noqa: E402,F401
