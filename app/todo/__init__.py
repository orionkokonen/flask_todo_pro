from flask import Blueprint

bp = Blueprint("todo", __name__, template_folder="templates")

from app.todo import routes  # noqa: E402,F401
