import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, csrf_token_for_session, make_session_token
from app.main import app
from config import settings


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def test_security_headers_present_on_login_page(client):
    resp = client.get("/login")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in resp.headers


def test_api_docs_are_disabled(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        resp = client.get(path)
        assert resp.status_code == 404


def test_root_redirects_to_login_with_forged_old_style_cookie(client, monkeypatch):
    import hashlib

    monkeypatch.setattr(settings, "dashboard_password", "secret")
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    monkeypatch.setattr(settings, "allow_no_auth", False)
    forged = hashlib.sha256(b"secret").hexdigest()
    client.cookies.set(COOKIE_NAME, forged)

    resp = client.get("/")

    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_root_returns_401_when_password_unset_and_no_auth_flag_unset(client, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "")
    monkeypatch.setattr(settings, "allow_no_auth", False)

    resp = client.get("/")

    assert resp.status_code == 401


def test_login_wrong_password_shows_error_message(client, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "secret")
    monkeypatch.setattr(settings, "session_secret", "test-secret")

    resp = client.post("/login", data={"password": "wrong"})

    assert resp.status_code == 401
    assert "Wrong password" in resp.text


def test_login_rate_limited_after_threshold(client, monkeypatch):
    from app.auth import LOGIN_RATE_LIMIT

    monkeypatch.setattr("app.auth._LOGIN_ATTEMPTS", {})
    monkeypatch.setattr(settings, "dashboard_password", "secret")
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    client.headers["X-Forwarded-For"] = "203.0.113.5"

    for _ in range(LOGIN_RATE_LIMIT):
        client.post("/login", data={"password": "wrong"})
    resp = client.post("/login", data={"password": "wrong"})

    assert resp.status_code == 429


def test_post_confirm_without_csrf_token_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "secret")
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    monkeypatch.setattr(settings, "allow_no_auth", False)
    session = make_session_token()
    client.cookies.set(COOKIE_NAME, session)

    resp = client.post(f"/email/some-id/confirm", data={"reason": "", "csrf_token": "wrong"})

    assert resp.status_code == 403


def test_logout_clears_cookie(client):
    resp = client.get("/logout")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
