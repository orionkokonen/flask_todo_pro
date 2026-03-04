from flask import Blueprint

bp = Blueprint("todo", __name__, template_folder="templates")

from app.todo import routes_board, routes_projects, routes_tasks, routes_teams  # noqa: E402,F401
