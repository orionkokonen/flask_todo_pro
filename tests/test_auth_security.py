"""認証セキュリティのテスト。

Open Redirect 脆弱性（ログイン後に外部 URL へ誘導される攻撃）の防御と、
パスワードポリシー（12文字以上・大文字・小文字・数字を各1文字以上）の回帰テスト。
next パラメータの同一オリジン検証と、文字種バリデーションがそれぞれ正しく機能しているかを確認する。
"""
from __future__ import annotations

from app.models import User


# パスワードポリシー違反時に返されるエラーメッセージを定数として定義する。
# テスト内にハードコードせず、将来メッセージが変わっても一箇所の修正で済むようにする。
PASSWORD_POLICY_MESSAGE = (
    "パスワードは12文字以上で、英大文字・英小文字・数字をそれぞれ1文字以上含めてください。"
).encode("utf-8")


def test_login_rejects_external_next_redirect(client, create_user):
    """攻撃者が next=https://evil.com を埋め込んだ場合に外部 URL へリダイレクトされないことを確認する。

    Open Redirect 攻撃（フィッシング誘導）のリグレッションテスト。
    ログイン成功後は必ずボードトップへ退避し、evil.com は Location に含まれてはならない。
    """
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
    """同一オリジンの相対パスは正規の遷移先として許可されることを確認する。

    ブロックしすぎて正規ユーザーの UX が壊れていないかの確認。
    """
    create_user("bob", "password123")

    response = client.post(
        "/auth/login?next=/todo/projects",
        data={"username": "bob", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/todo/projects")


def test_register_rejects_password_shorter_than_min_length(app, client):
    """12 文字未満のパスワードで登録が拒否され、DB にユーザーが作られないことを確認する。"""
    response = client.post(
        "/auth/register",
        data={
            "username": "short_pw_user",
            "password": "StrongPas12",
            "password2": "StrongPas12",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert PASSWORD_POLICY_MESSAGE in response.data

    with app.app_context():
        assert User.query.filter_by(username="short_pw_user").first() is None


def test_register_rejects_password_without_uppercase(app, client):
    """英大文字を含まないパスワードで登録が拒否されることを確認する。"""
    response = client.post(
        "/auth/register",
        data={
            "username": "missing_upper_user",
            "password": "strongpass123",
            "password2": "strongpass123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert PASSWORD_POLICY_MESSAGE in response.data

    with app.app_context():
        assert User.query.filter_by(username="missing_upper_user").first() is None


def test_register_rejects_password_without_lowercase(app, client):
    """英小文字を含まないパスワードで登録が拒否されることを確認する。"""
    response = client.post(
        "/auth/register",
        data={
            "username": "missing_lower_user",
            "password": "STRONGPASS123",
            "password2": "STRONGPASS123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert PASSWORD_POLICY_MESSAGE in response.data

    with app.app_context():
        assert User.query.filter_by(username="missing_lower_user").first() is None


def test_register_rejects_password_without_digit(app, client):
    """数字を含まないパスワードで登録が拒否されることを確認する。"""
    response = client.post(
        "/auth/register",
        data={
            "username": "missing_digit_user",
            "password": "StrongPassword",
            "password2": "StrongPassword",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert PASSWORD_POLICY_MESSAGE in response.data

    with app.app_context():
        assert User.query.filter_by(username="missing_digit_user").first() is None


def test_register_accepts_password_with_min_length(app, client):
    """全ポリシーを満たすパスワードで登録が成功し、DB にユーザーが正しく保存されることを確認する。

    パスワードはハッシュ化されて保存されるため、check_password() で検証し、
    平文が保存されていないことも間接的に確認している。
    また、登録成功後は自動ログインしてボードへリダイレクトされるため、
    遷移先が /todo/ であることも合わせて検証する。
    """
    response = client.post(
        "/auth/register",
        data={
            "username": "min_length_user",
            "password": "StrongPass123",
            "password2": "StrongPass123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/todo/")

    with app.app_context():
        user = User.query.filter_by(username="min_length_user").first()
        assert user is not None
        assert user.check_password("StrongPass123")


def test_register_logs_in_user_and_shows_success_flash(client):
    """登録成功後に自動ログインされ、成功フラッシュメッセージが表示されることを確認する。

    登録直後にユーザーがログイン済みになっているかを、
    /todo/ へのアクセスが認証なしで 200 を返すことで間接的に検証する。
    「登録 → ログイン」と 2 ステップ踏まなくてよい UX 設計が
    正しく機能しているかのリグレッションテスト。
    """
    # 登録成功時に表示される期待メッセージを、読みやすいように変数へ切り出す。
    # この固定文字列と実際のレスポンスを比較することで、文言変更時にテストが失敗して検知できる。
    success_message = (
        "\u767b\u9332\u304c\u5b8c\u4e86\u3057\u307e\u3057\u305f\u3002"
        "\u30ed\u30b0\u30a4\u30f3\u3057\u307e\u3057\u305f\u3002"
    )

    response = client.post(
        "/auth/register",
        data={
            "username": "new_logged_in_user",
            "password": "StrongPass123",
            "password2": "StrongPass123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert success_message in response.get_data(as_text=True)

    # 登録後にそのままボードへアクセスできる（ログイン済み）ことを確認する。
    # ログインしていなければ /auth/login にリダイレクトされ 302 が返るため、
    # 200 が返ることで「自動ログインが成功した」と判定できる。
    board_response = client.get("/todo/", follow_redirects=False)

    assert board_response.status_code == 200
