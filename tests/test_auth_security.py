"""認証セキュリティのテスト。

Open Redirect 脆弱性（ログイン後に外部 URL へ誘導される攻撃）が
防がれていることを確認する。
next パラメータの同一オリジン検証が正しく動作しているかの回帰テスト。
"""
from __future__ import annotations

from app.models import User


def test_login_rejects_external_next_redirect(client, create_user):
    # 攻撃者が next=https://evil.com を埋め込んだリンクを踏ませた場合に、
    # 外部 URL へのリダイレクトがブロックされ、ボードトップへ戻ることを確認する。
    create_user("alice", "password123")

    response = client.post(
        "/auth/login?next=https://evil.com",
        data={"username": "alice", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/todo/")
    assert "evil.com" not in response.headers["Location"]


def test_login_allows_safe_relative_next_redirect(client, create_user):
    # 同一オリジンの相対パスは正規の遷移先として許可されることを確認する。
    # ブロックしすぎて UX が壊れていないかの検証でもある。
    create_user("bob", "password123")

    response = client.post(
        "/auth/login?next=/todo/projects",
        data={"username": "bob", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/todo/projects")


def test_register_rejects_password_shorter_than_min_length(app, client):
    response = client.post(
        "/auth/register",
        data={
            "username": "short_pw_user",
            "password": "1234567",
            "password2": "1234567",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "パスワードは8文字以上で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert User.query.filter_by(username="short_pw_user").first() is None


def test_register_accepts_password_with_min_length(app, client):
    response = client.post(
        "/auth/register",
        data={
            "username": "min_length_user",
            "password": "12345678",
            "password2": "12345678",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    with app.app_context():
        user = User.query.filter_by(username="min_length_user").first()
        assert user is not None
        assert user.check_password("12345678")
