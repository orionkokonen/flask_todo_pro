from __future__ import annotations

import pytest

from app import create_app


def test_create_app_requires_secret_key_when_env_missing(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"TESTING": True})
