"""レート制限の動作テスト。

認証系エンドポイントへの短時間連続試行がブロックされること、
成功ログインでカウンターがリセットされることを回帰的に確認する。
加えて、ProxyFix の有効・無効による X-Forwarded-For の扱いの違いも検証する。
レート制限は in-memory のため、autouse fixture が各テスト前後でリセットしている。
"""
from __future__ import annotations


def _post_weak_registration(client, username: str, forwarded_for: str | None = None):
    """パスワードポリシー違反のリクエストをヘルパーとして送る。

    X-Forwarded-For ヘッダーを任意で付与できるようにしており、
    ProxyFix の挙動（ヘッダーを信用するか無視するか）を切り替えるテストで使う。
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


def test_login_rate_limit_blocks_after_too_many_failures(client, create_user):
    """ログイン失敗が制限回数（5回）を超えると 429 が返り、Retry-After ヘッダーが付くことを確認する。

    6 回目で初めてブロックされること（5 回までは通過すること）も検証し、
    設定値の境界が正しく機能しているかをアサートする。
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
    """ログイン成功後にカウンターがリセットされ、再び失敗を規定回数まで受け付けることを確認する。

    成功後もカウントが残ったままだと、正規ユーザーが過去の失敗分でロックアウトされる
    誤検知が起きる。リセット動作は UX に直結するため重要な回帰テスト対象。
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
    """登録失敗が制限回数（6回）を超えると 429 が返ることを確認する。

    パスワードポリシー違反（7文字・全小文字）で失敗させてカウントを積み上げている。
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
    """ProxyFix が無効（TRUSTED_HOPS=0）のとき、X-Forwarded-For を信用しないことを確認する。

    クライアントが X-Forwarded-For を偽装して別の IP に見せかけてもカウントが同じバケットに
    積まれ、ブロックが正常に機能することをアサートする（IP 偽装によるレート制限回避の防止）。
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
    """ProxyFix が有効（TRUSTED_HOPS=1）のとき、X-Forwarded-For が IP として使われることを確認する。

    異なる IP アドレス（2.2.2.2）からのリクエストは別バケットとして扱われ、ブロックされない。
    同じ IP（1.1.1.1）からの 7 回目はブロックされることで、IP ごとの独立したカウントを検証する。
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
