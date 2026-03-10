"""認証セキュリティのテスト。

Open Redirect 脆弱性（ログイン後に外部 URL へ誘導される攻撃）の防御と、
パスワードポリシー（12文字以上・大文字・小文字・数字を各1文字以上）の回帰テスト。
next パラメータの同一オリジン検証と、文字種バリデーションがそれぞれ正しく機能しているかを確認する。
"""
from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError

import app.auth.routes as auth_routes
from app import db
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


def test_login_success_writes_audit_log(client, create_user, caplog):
    """ログイン成功を監査ログに残していることを確認する。

    「誰がいつ入れたか」を後で追えるようにする、安全面の回帰テスト。
    """
    create_user("audit_success_user", "password123")
    caplog.set_level(logging.INFO)

    response = client.post(
        "/auth/login",
        data={"username": "audit_success_user", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "login succeeded:" in caplog.text
    assert "username=audit_success_user" in caplog.text


def test_login_failure_writes_audit_log(client, create_user, caplog):
    """ログイン失敗も監査ログに残していることを確認する。

    不正試行の痕跡が残るかを見ておくと、攻撃調査の手がかりを失いにくい。
    """
    create_user("audit_failed_user", "password123")
    caplog.set_level(logging.WARNING)

    response = client.post(
        "/auth/login",
        data={"username": "audit_failed_user", "password": "wrong-password"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "login failed:" in caplog.text
    assert "username=audit_failed_user" in caplog.text


def test_login_unknown_user_runs_dummy_hash_check(client, monkeypatch):
    """存在しないユーザーでもタイミング調整用ハッシュで照合することを確認する。

    「存在する時だけ照合する」実装だと処理時間の差から
    アカウント有無を推測されやすくなるため、その差を小さくする仕組みの確認。
    """
    calls: list[tuple[str, str]] = []
    original = auth_routes.check_password_hash

    def tracking_check_password_hash(password_hash: str, password: str) -> bool:
        # 本物の関数はそのまま実行しつつ、「どの値で呼ばれたか」だけ記録する。
        calls.append((password_hash, password))
        return original(password_hash, password)

    monkeypatch.setattr(auth_routes, "check_password_hash", tracking_check_password_hash)

    response = client.post(
        "/auth/login",
        data={"username": "missing-user", "password": "WrongPass123"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert calls == [(auth_routes._TIMING_EQUALIZATION_HASH, "WrongPass123")]


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
    # 文言を変数へ出しておくと、「何を期待しているテストか」が読み取りやすい。
    # 画面の文言が意図せず変わった時も、この比較で気づける。
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

    # 登録後にそのままボードへアクセスできるなら、ログイン状態が作られていると分かる。
    # 未ログインなら /auth/login へ飛ばされるはずなので、200 が返ること自体が確認材料になる。
    board_response = client.get("/todo/", follow_redirects=False)

    assert board_response.status_code == 200


def test_register_success_writes_audit_log(client, caplog):
    """登録成功時に監査ログを書き、作成ユーザー名が記録されることを確認する。"""
    caplog.set_level(logging.INFO)

    response = client.post(
        "/auth/register",
        data={
            "username": "register_audit_success",
            "password": "StrongPass123",
            "password2": "StrongPass123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "register succeeded:" in caplog.text
    assert "username=register_audit_success" in caplog.text


def test_register_stores_password_hash_with_scrypt(app, client):
    """登録時のパスワードハッシュ方式が scrypt で固定されていることを確認する。

    Werkzeug の既定値変更に影響されず、面接でもハッシュ方式を説明できる状態を
    回帰テストで固定する。
    """
    response = client.post(
        "/auth/register",
        data={
            "username": "scrypt_user",
            "password": "StrongPass123",
            "password2": "StrongPass123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        user = User.query.filter_by(username="scrypt_user").first()
        assert user is not None
        # Werkzeug は "scrypt:..." / "pbkdf2:sha256:..." のようにプレフィックスでアルゴリズムを識別する。
        # このテストでプレフィックスを固定することで、将来 Werkzeug のデフォルトが変わったとき
        # に意図せずハッシュ方式が切り替わるリグレッションをテストで検知できる。
        assert user.password_hash.startswith("scrypt:")


def test_register_duplicate_username_shows_generic_message(client, create_user):
    """重複ユーザー名でも存在有無を直接示さないメッセージを返す。

    画面上の言い方が変わると列挙対策が崩れるため、文言も回帰テストで固定する。
    """
    create_user("duplicated_user", "password123")

    response = client.post(
        "/auth/register",
        data={
            "username": "duplicated_user",
            "password": "StrongPass123",
            "password2": "StrongPass123",
        },
        follow_redirects=False,
    )

    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "登録内容を確認して、別のユーザー名で再試行してください。" in body
    assert "このユーザー名は既に使用されています。" not in body


def test_register_commit_error_rolls_back_and_shows_generic_flash(
    app,
    client,
    monkeypatch,
):
    """登録時の DB 書き込み失敗で rollback し、次の処理へ壊れたセッションを残さない。

    monkeypatch で commit() を 1 回だけ失敗させ、失敗後に回復できるかを見る。
    """
    rollback_called = False
    original_commit = db.session.commit
    original_rollback = db.session.rollback
    state = {"failed_once": False}

    def flaky_commit():
        # 1 回目だけわざと失敗させる。2 回目以降は本物の commit() を使う。
        if not state["failed_once"]:
            state["failed_once"] = True
            raise SQLAlchemyError("forced failure")
        return original_commit()

    def tracking_rollback():
        # rollback() が本当に呼ばれたかを記録しつつ、中身は元の実装へ流す。
        nonlocal rollback_called
        rollback_called = True
        return original_rollback()

    monkeypatch.setattr(db.session, "commit", flaky_commit)
    monkeypatch.setattr(db.session, "rollback", tracking_rollback)

    response = client.post(
        "/auth/register",
        data={
            "username": "commit_error_user",
            "password": "StrongPass123",
            "password2": "StrongPass123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert rollback_called is True
    assert "登録を完了できませんでした。入力内容を確認して再試行してください。" in (
        response.get_data(as_text=True)
    )

    with app.app_context():
        assert User.query.filter_by(username="commit_error_user").first() is None

        # 失敗後にも普通の保存ができれば、「PendingRollbackError を残していない」と判断できる。
        recovery_user = User(username="post_error_recovery_user")
        recovery_user.set_password("StrongPass123")
        db.session.add(recovery_user)
        db.session.commit()

        assert User.query.filter_by(username="post_error_recovery_user").first() is not None


def test_register_failure_writes_audit_log(client, monkeypatch, caplog):
    """登録失敗時に監査ログを書き、失敗したユーザー名が記録されることを確認する。"""
    original_commit = db.session.commit
    state = {"failed_once": False}

    def flaky_commit():
        if not state["failed_once"]:
            state["failed_once"] = True
            raise SQLAlchemyError("forced failure")
        return original_commit()

    monkeypatch.setattr(db.session, "commit", flaky_commit)
    caplog.set_level(logging.WARNING)

    response = client.post(
        "/auth/register",
        data={
            "username": "register_audit_failed",
            "password": "StrongPass123",
            "password2": "StrongPass123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "register failed:" in caplog.text
    assert "username=register_audit_failed" in caplog.text
