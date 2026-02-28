from __future__ import annotations


def test_login_rate_limit_blocks_after_too_many_failures(client, create_user):
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
    assert "試行回数が多すぎます。少し時間を置いて再試行してください。".encode("utf-8") in blocked.data


def test_successful_login_resets_rate_limit_counter(client, create_user):
    create_user("reset_user", "password123")

    for _ in range(4):
        response = client.post(
            "/auth/login",
            data={"username": "reset_user", "password": "wrong-password"},
            follow_redirects=False,
        )
        assert response.status_code == 200

    success = client.post(
        "/auth/login",
        data={"username": "reset_user", "password": "password123"},
        follow_redirects=False,
    )
    assert success.status_code == 302

    for _ in range(5):
        response = client.post(
            "/auth/login",
            data={"username": "reset_user", "password": "wrong-password"},
            follow_redirects=False,
        )
        assert response.status_code == 200


def test_register_rate_limit_blocks_after_too_many_failures(client):
    for idx in range(3):
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
