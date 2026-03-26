# このファイルはログイン機能の部品を Flask に登録するファイルです。
"""認証機能用 Blueprint パッケージ。

Blueprint は URL を機能ごとにまとめるための仕組みで、
このパッケージではログイン・登録・ログアウト関連だけを担当する。
"""
from flask import Blueprint

# Blueprint（ルーティングのグループ）を定義し、後からルートをインポートする。
# routes.py を先頭でインポートすると bp がまだ未定義で循環インポートになるため、
# bp 定義の後にインポートするのが Flask Blueprint の慣例パターン。
bp = Blueprint("auth", __name__, template_folder="templates")

from app.auth import routes  # noqa: E402,F401
