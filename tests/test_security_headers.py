# このファイルはセキュリティ用ヘッダーが正しく付くかを確かめるテストです。
"""セキュリティヘッダーと静的アセット参照の回帰テスト。

after_request フックで全レスポンスに付与されるヘッダーの存在・値を確認する。
Bootstrap をローカル配信に切り替えたため、CSP が self 中心の構成を維持し、
テンプレートが CDN ではなく /static/vendor/... を参照していることも検証する。
テスト設定（TESTING=True）では HSTS を出力せず、
本番相当設定（TESTING=False / DEBUG=False）では HSTS を返すことも検証する。
"""
from __future__ import annotations


def test_security_headers_are_set_on_responses(client):
    """必須セキュリティヘッダーが付与され、CSP が期待する構成であることを確認する。

    特に script-src に 'unsafe-inline' が含まれていないことをアサートする。
    inline event handler を app.js の data-confirm に移行した成果として、
    XSS で任意スクリプトを実行されるリスクを下げた状態を回帰テストで固定する。
    """
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    # script-src は self のみ許可し、unsafe-inline は含まない
    assert "script-src 'self'" in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp
    # style-src はインライン style 互換のため unsafe-inline を維持
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "font-src 'self'" in csp
    assert "cdn.jsdelivr.net" not in csp
    assert "upgrade-insecure-requests" not in csp
    # テスト環境では SESSION_COOKIE_SECURE=False のため HSTS は付与されない
    assert "Strict-Transport-Security" not in response.headers


def test_login_page_uses_local_vendor_assets(client):
    """ログイン画面が CDN ではなくローカル配信の vendor 資産を参照することを確認する。

    外部 CDN の到達性に依存しないようにし、PC / スマホで見た目が崩れにくい構成を
    テンプレート出力レベルで回帰テストする。
    """
    response = client.get("/auth/login")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    # /static/vendor/... への参照が HTML に含まれることで、ローカル配信への切り替えが完了しているか確認する。
    assert '/static/vendor/bootstrap/bootstrap.min.css' in html
    assert '/static/vendor/bootstrap-icons/bootstrap-icons.min.css' in html
    assert '/static/vendor/bootstrap/bootstrap.bundle.min.js' in html
    # 誰かが誤って CDN の link タグを追加・戻してしまったときに、このテストが失敗して検知できる。
    assert 'cdn.jsdelivr.net' not in html


def test_login_sets_session_cookie_security_attributes(client, create_user):
    """ログイン成功時の Set-Cookie に HttpOnly と SameSite=Lax が付いていることを確認する。

    テスト環境（TESTING=True / HTTP）では Secure 属性は付かないことも合わせて確認する。
    Secure 属性の有無を環境別に制御することで、ローカル HTTP 開発中に Cookie が送られず
    ログインできなくなる問題を防いでいる。
    """
    create_user("cookie_user", "password123")

    response = client.post(
        "/auth/login",
        data={
            "username": "cookie_user",
            "password": "password123",
        },
        follow_redirects=False,
    )

    cookies = response.headers.getlist("Set-Cookie")

    assert response.status_code == 302
    assert any("session=" in cookie for cookie in cookies)
    assert any("HttpOnly" in cookie for cookie in cookies)
    assert any("SameSite=Lax" in cookie for cookie in cookies)
    assert not any("Secure" in cookie for cookie in cookies)


def test_login_sets_remember_cookie_duration(client, create_user):
    """remember_me チェック時に発行される Cookie に有効期限が設定されていることを確認する。

    REMEMBER_COOKIE_DURATION=30日 を明示設定しているため、
    デフォルト任せ（365日）にならず、期限が存在することを回帰テストで保証する。
    """
    create_user("remember_user", "password123")

    response = client.post(
        "/auth/login",
        data={
            "username": "remember_user",
            "password": "password123",
            "remember_me": "y",
        },
        follow_redirects=False,
    )

    cookies = response.headers.getlist("Set-Cookie")
    remember_cookie = next((cookie for cookie in cookies if "remember_token=" in cookie), "")

    assert response.status_code == 302
    assert remember_cookie
    assert "HttpOnly" in remember_cookie
    assert "SameSite=Lax" in remember_cookie
    assert "Expires=" in remember_cookie or "Max-Age=" in remember_cookie


def test_hsts_is_enabled_when_secure_cookies_are_enabled(app_factory):
    """本番相当設定（Secure cookie 有効）のとき HSTS ヘッダーが返ることを確認する。

    HSTS は HTTPS 環境のみで意味を持つため、TESTING=False かつ DEBUG=False のときだけ付与する設計。
    開発・テスト中に HSTS が出てしまうと、HTTP でアクセスしたブラウザが
    以降 HTTPS を強制し続けて開発できなくなるリスクがあるため、条件分岐は重要な回帰テスト対象。
    """
    app = app_factory(
        {
            "TESTING": False,
            "DEBUG": False,
            "SECRET_KEY": "prod-secret",
        }
    )
    client = app.test_client()

    response = client.get("/auth/login")

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    # 本番相当では mixed content（https ページ内の http 読み込み）を避ける指示も有効になる。
    assert "upgrade-insecure-requests" in response.headers["Content-Security-Policy"]
