from __future__ import annotations

from app import db
from app.models import User


def _create_user(username: str, password: str) -> None:
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()


def test_login_rejects_external_next_redirect(app, client):
    with app.app_context():
        _create_user("alice", "password123")

    response = client.post(
        "/auth/login?next=https://evil.com",
        data={"username": "alice", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/todo/")
    assert "evil.com" not in response.headers["Location"]


def test_login_allows_safe_relative_next_redirect(app, client):
    with app.app_context():
        _create_user("bob", "password123")

    response = client.post(
        "/auth/login?next=/todo/projects",
        data={"username": "bob", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/todo/projects")
