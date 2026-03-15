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


def test_create_app_sets_testing_cookie_security_defaults():
    """テスト環境では安全性を保ちつつ、HTTP ローカル実行が詰まらない設定になることを確認する。"""
    # TESTING=True では「安全にしつつもローカル HTTP で動かせるか」が大事。
    # ここが本番向けの強い設定のままだと、テスト中に Cookie が送られずログインできなくなる。
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret"})

    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["REMEMBER_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["REMEMBER_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert app.config["REMEMBER_COOKIE_SECURE"] is False
    assert app.config["PASSWORD_MIN_LENGTH"] == 12
    assert app.config["REMEMBER_COOKIE_DURATION"].days == 30
    assert app.config["PROXY_FIX_TRUSTED_HOPS"] == 0


def test_create_app_sets_secure_cookies_for_non_testing_app():
    """本番相当では Cookie に Secure が付くことを確認する。"""
    # 本番相当では HTTPS 前提に寄せ、通信中に Cookie が漏れにくい設定へ切り替わるかを見る。
    app = create_app({"SECRET_KEY": "test-secret"})

    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["REMEMBER_COOKIE_SECURE"] is True
