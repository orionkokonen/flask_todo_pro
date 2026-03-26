# このファイルはログイン回数制限が正しく動くかを確かめるテストです。
"""レート制限（ブルートフォース対策）の動作テスト。

検証ポイント:
- ログイン / 登録の失敗が制限回数を超えると 429（Too Many Requests）が返る
- ログイン成功でカウンターがリセットされる（正規ユーザーがロックアウトされない）
- ProxyFix 無効時は X-Forwarded-For を無視し、有効時は IP 別にカウントする
レート制限はメモリ内管理で、conftest.py の autouse fixture が毎テストごとにリセットする。
"""
from __future__ import annotations

import app.security as security_module


def _post_weak_registration(client, username: str, forwarded_for: str | None = None):
    """わざとパスワードポリシー違反の登録リクエストを送るヘルパー。

    forwarded_for を指定すると X-Forwarded-For ヘッダーが付き、
    ProxyFix が IP をどう扱うかのテストに使える。
    """
    headers = {}
    if forwarded_for is not None:
        headers["X-Forwarded-For"] = forwarded_for

    return client.post(
        "/auth/register",
        data={
            "username": username,
            "password": "lowercaseonly",
            "password2": "lowercaseonly",
        },
        headers=headers,
        follow_redirects=False,
    )


def test_rate_limiter_prune_removes_empty_bucket(monkeypatch):
    """期限切れで空になったバケットは内部辞書から削除される。

    これが無いと、もう使われない IP の記録だけが少しずつ残り続ける。
    """
    limiter = security_module.SimpleRateLimiter()
    times = iter([0.0, 61.0])
    monkeypatch.setattr(security_module, "monotonic", lambda: next(times))

    limiter.record_failure("login:127.0.0.1", window_seconds=60)

    allowed, retry_after = limiter.check("login:127.0.0.1", limit=5, window_seconds=60)

    assert allowed is True
    assert retry_after == 0
    assert "login:127.0.0.1" not in limiter._entries


def test_login_rate_limit_blocks_after_too_many_failures(client, create_user):
    """ログイン失敗が 5 回を超えると 429 になり、Retry-After ヘッダーが付くことを確認。

    境界値テスト: 5 回目まで 200、6 回目で 429 → 設定値どおり動いているか検証。
    """
    create_user("limited_user", "password123")

    for _ in range(5):
        response = client.post(
            "/auth/login",
            data={"username": "limited_user", "password": "wrong-password"},
            follow_redirects=False,
        )
        assert response.status_code == 200

    blocked = client.post(
        "/auth/login",
        data={"username": "limited_user", "password": "wrong-password"},
        follow_redirects=False,
    )

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_successful_login_resets_rate_limit_counter(client, create_user):
    """ログイン成功後にカウンターがリセットされ、再び 5 回まで失敗できることを確認。

    リセットしないと正規ユーザーが過去の失敗分でロックされてしまう（誤ブロック）。
    """
    create_user("reset_user", "password123")

    for _ in range(4):
        response = client.post(
            "/auth/login",
            data={"username": "reset_user", "password": "wrong-password"},
            follow_redirects=False,
        )
        assert response.status_code == 200

    # 成功ログインでカウンターがリセットされることを確認する
    success = client.post(
        "/auth/login",
        data={"username": "reset_user", "password": "password123"},
        follow_redirects=False,
    )
    assert success.status_code == 302

    # リセット後は再び 5 回まで失敗を受け付けるはず
    for _ in range(5):
        response = client.post(
            "/auth/login",
            data={"username": "reset_user", "password": "wrong-password"},
            follow_redirects=False,
        )
        assert response.status_code == 200


def test_register_rate_limit_blocks_after_too_many_failures(client):
    """登録失敗が 6 回を超えると 429 が返ることを確認。

    パスワードポリシー違反（7 文字・全小文字）でわざと失敗させてカウントを積み上げる。
    """
    for idx in range(6):
        response = client.post(
            "/auth/register",
            data={
                "username": f"short_user_{idx}",
                "password": "1234567",
                "password2": "1234567",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200

    blocked = client.post(
        "/auth/register",
        data={
            "username": "short_user_blocked",
            "password": "1234567",
            "password2": "1234567",
        },
        follow_redirects=False,
    )

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_register_rate_limit_ignores_untrusted_forwarded_for_header(app_factory):
    """ProxyFix 無効時は X-Forwarded-For ヘッダーを無視することを確認。

    攻撃者が IP を偽装（1.1.1.1 → 2.2.2.2）しても同じバケットにカウントされ、
    レート制限を回避できないことを検証する。
    """
    app = app_factory({"PROXY_FIX_TRUSTED_HOPS": 0})
    client = app.test_client()

    for idx in range(6):
        response = _post_weak_registration(client, f"spoofed_{idx}", forwarded_for="1.1.1.1")
        assert response.status_code == 200

    # X-Forwarded-For を別の IP に変えてもブロックされるはず
    blocked = _post_weak_registration(client, "spoofed_blocked", forwarded_for="2.2.2.2")

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_register_rate_limit_uses_forwarded_for_when_proxy_fix_enabled(app_factory):
    """ProxyFix 有効時は X-Forwarded-For の IP ごとに独立してカウントされることを確認。

    1.1.1.1 で 6 回失敗 → 2.2.2.2 は別カウントなので通過、1.1.1.1 の 7 回目はブロック。
    """
    app = app_factory({"PROXY_FIX_TRUSTED_HOPS": 1})
    client = app.test_client()

    for idx in range(6):
        response = _post_weak_registration(client, f"forwarded_{idx}", forwarded_for="1.1.1.1")
        assert response.status_code == 200

    # 別の IP からのリクエストは別バケットなので通過するはず
    allowed = _post_weak_registration(client, "forwarded_other_ip", forwarded_for="2.2.2.2")
    # 同じ IP（1.1.1.1）の 7 回目はブロックされるはず
    blocked = _post_weak_registration(client, "forwarded_blocked", forwarded_for="1.1.1.1")

    assert allowed.status_code == 200
    assert blocked.status_code == 429
