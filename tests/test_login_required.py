"""ログイン必須ルートの回帰テスト。

未ログイン状態で主要保護ページにアクセスしたとき、
ログイン画面へリダイレクトされ、かつ元の URL が next= に保持されることを確認する。
@login_required デコレータの抜けを継続的に検知するための安全網。
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/todo/",
        "/todo/tasks/new",
        "/todo/projects",
        "/todo/teams",
    ],
)
def test_protected_routes_redirect_to_login(client, path):
    """保護ページは未ログイン時にログイン画面へ逃がすことを確認する。"""
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 302

    parsed = urlparse(response.headers["Location"])
    assert parsed.path.endswith("/auth/login")
    # next= に元の URL が含まれていることで、ログイン後に元のページへ戻れる。
    assert parse_qs(parsed.query)["next"] == [path]
