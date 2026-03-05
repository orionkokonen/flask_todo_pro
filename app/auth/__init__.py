from flask import Blueprint

# Blueprint（ルーティングのグループ）を定義し、後からルートをインポートする。
# routes.py を先頭でインポートすると bp がまだ未定義で循環インポートになるため、
# bp 定義の後にインポートするのが Flask Blueprint の慣例パターン。
bp = Blueprint("auth", __name__, template_folder="templates")

from app.auth import routes  # noqa: E402,F401
