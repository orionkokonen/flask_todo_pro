from __future__ import annotations


def test_login_form_renders_with_csrf_enabled(csrf_client):
    response = csrf_client.get("/auth/login")

    assert response.status_code == 200


def test_login_post_without_csrf_token_is_rejected(csrf_client):
    response = csrf_client.post(
        "/auth/login",
        data={"username": "alice", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 400
