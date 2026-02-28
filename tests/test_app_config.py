"""アプリ起動設定のテスト。

SECRET_KEY が必須であることを確認する。
セキュリティ上の設定漏れが起動時点で検知できるかを回帰テストで保証する。
"""
from __future__ import annotations

import pytest

from app import create_app


def test_create_app_requires_secret_key_when_env_missing(monkeypatch):
    # SECRET_KEY が環境変数に存在しない状態を再現し、アプリが安全に起動拒否することを確認する。
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"TESTING": True})
