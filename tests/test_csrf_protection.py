# このファイルは CSRF 対策が正しく動くかを確かめるテストです。
"""CSRF 保護の動作テスト。

通常テストは WTF_CSRF_ENABLED=False で動かしているため、
CSRF 検証を有効にした専用フィクスチャ（csrf_client）を使い、
トークンなしの POST が 400 で弾かれることを回帰テストする。
ログアウトも GET から POST + CSRF に変更されたため、その保護も検証する。
"""
from __future__ import annotations

import re

from app import db
from app.models import User


def _create_user(app, username: str, password: str) -> None:
    """CSRF 有効アプリに直接ユーザーを作成するヘルパー。

    csrf_client 経由の登録は CSRF トークンが必要で複雑になるため、
    DB に直接 insert することでセットアップを簡潔にしている。
    """
    with app.app_context():
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def _extract_csrf_token(response) -> str:
    """レスポンス HTML から CSRF トークン値を正規表現で取り出すヘルパー。

    Flask-WTF が hidden フィールドとして埋め込んだトークンを取得し、
    次のリクエストに含める用途で使う。
    """
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"',
        response.data.decode("utf-8"),
    )
    assert match is not None
    return match.group(1)


def test_login_form_renders_with_csrf_enabled(csrf_client):
    """CSRF 有効設定でもログインフォームの GET リクエストが正常に返ることを確認する。

    CSRF 保護は POST にのみ適用される。GET が 200 を返さなければ
    設定が過剰に制限されていることになるため、この確認も必要。
    """
    response = csrf_client.get("/auth/login")

    assert response.status_code == 200


def test_login_post_without_csrf_token_is_rejected(csrf_client):
    """CSRF トークンを含まない POST リクエストは 400 で拒否されることを確認する。

    第三者サイトのフォームから送られる POST にはトークンが含まれないため、
    Flask-WTF がこれを弾いて CSRF 攻撃を防ぐ。
    この動作が失われると、ログインや操作系エンドポイントが CSRF に無防備になる。
    """
    response = csrf_client.post(
        "/auth/login",
        data={"username": "alice", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 400


def test_logout_get_is_not_allowed(csrf_client):
    """ログアウトエンドポイントが GET を受け付けないことを確認する。

    POST 専用にすることで、攻撃者が仕込んだリンクを踏むだけで強制ログアウトされる
    CSRF を防いでいる。GET を誤って許可していないかの回帰テスト。
    """
    response = csrf_client.get("/auth/logout")

    assert response.status_code == 405


def test_logout_post_requires_csrf_token_and_logs_user_out(csrf_app, csrf_client):
    """ログアウトが正しい CSRF トークンを要求し、成功後に認証済みページへアクセスできなくなることを確認する。

    フロー:
    1. ログインフォームから CSRF トークンを取得してログインする
    2. CSRF トークンなしのログアウト POST は 400 で拒否されることを確認する
    3. ボード画面から CSRF トークンを取得して正規にログアウトする
    4. 認証が必要なページへのアクセスがログイン画面にリダイレクトされることを確認する
    """
    _create_user(csrf_app, "csrf_user", "password123")

    # 1. ログインフォームからトークンを取得してログインする
    login_form = csrf_client.get("/auth/login")
    login_token = _extract_csrf_token(login_form)

    login_response = csrf_client.post(
        "/auth/login",
        data={
            "username": "csrf_user",
            "password": "password123",
            "csrf_token": login_token,
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    # 2. CSRF トークンなしのログアウトは拒否される
    missing_token = csrf_client.post("/auth/logout", follow_redirects=False)
    assert missing_token.status_code == 400

    # 3. 正規のトークンでログアウトする
    board = csrf_client.get("/todo/")
    assert board.status_code == 200
    logout_token = _extract_csrf_token(board)

    logout_response = csrf_client.post(
        "/auth/logout",
        data={"csrf_token": logout_token},
        follow_redirects=False,
    )

    assert logout_response.status_code == 302
    assert logout_response.headers["Location"].endswith("/auth/login")

    # 4. ログアウト後は認証が必要なページにアクセスできない
    followup = csrf_client.get("/todo/", follow_redirects=False)
    assert followup.status_code == 302
    assert "/auth/login" in followup.headers["Location"]
