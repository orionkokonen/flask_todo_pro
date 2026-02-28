from __future__ import annotations


def test_security_headers_are_set_on_responses(client):
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "https://cdn.jsdelivr.net" in csp
    assert "'unsafe-inline'" in csp
    assert "Strict-Transport-Security" not in response.headers


def test_login_sets_session_cookie_security_attributes(client, create_user):
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


def test_hsts_is_enabled_when_secure_cookies_are_enabled(app_factory):
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
