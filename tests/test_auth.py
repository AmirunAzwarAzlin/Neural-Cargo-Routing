import pytest
from fastapi import HTTPException

from app.auth import require_auth
from config import settings


def test_require_auth_fails_closed_when_password_empty(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "")
    monkeypatch.setattr(settings, "allow_no_auth", False)
    with pytest.raises(HTTPException) as exc_info:
        require_auth(sdoc_session=None)
    assert exc_info.value.status_code == 401


def test_require_auth_allows_bypass_when_flag_set(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "")
    monkeypatch.setattr(settings, "allow_no_auth", True)
    require_auth(sdoc_session=None)  # must not raise


def test_require_auth_redirects_to_login_on_bad_session(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "secret")
    with pytest.raises(HTTPException) as exc_info:
        require_auth(sdoc_session="wrong-token")
    assert exc_info.value.status_code == 303


def test_valid_session_token_round_trips(monkeypatch):
    from app.auth import make_session_token

    monkeypatch.setattr(settings, "dashboard_password", "secret")
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    token = make_session_token()
    assert require_auth(sdoc_session=token) == token


def test_expired_session_token_is_rejected(monkeypatch):
    import time as time_module

    from app.auth import make_session_token

    monkeypatch.setattr(settings, "dashboard_password", "secret")
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    real_time = time_module.time
    monkeypatch.setattr(time_module, "time", lambda: real_time() - 100_000)
    stale_token = make_session_token()
    monkeypatch.setattr(time_module, "time", real_time)

    with pytest.raises(HTTPException) as exc_info:
        require_auth(sdoc_session=stale_token)
    assert exc_info.value.status_code == 303


def test_old_style_password_hash_cookie_is_rejected(monkeypatch):
    import hashlib

    monkeypatch.setattr(settings, "dashboard_password", "secret")
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    forged = hashlib.sha256(b"secret").hexdigest()

    with pytest.raises(HTTPException) as exc_info:
        require_auth(sdoc_session=forged)
    assert exc_info.value.status_code == 303


def test_check_password_handles_non_ascii_without_raising(monkeypatch):
    from app.auth import check_password

    monkeypatch.setattr(settings, "dashboard_password", "pässwörd")
    assert check_password("pässwörd") is True
    assert check_password("wrong") is False


def test_csrf_token_round_trips_and_rejects_mismatch(monkeypatch):
    from app.auth import csrf_token_for_session, make_session_token, require_csrf

    monkeypatch.setattr(settings, "session_secret", "test-secret")
    session = make_session_token()
    token = csrf_token_for_session(session)

    require_csrf(token, session)  # must not raise

    with pytest.raises(HTTPException) as exc_info:
        require_csrf("wrong-token", session)
    assert exc_info.value.status_code == 403


def test_require_csrf_skips_check_in_no_auth_mode():
    from app.auth import require_csrf

    require_csrf("", "")  # empty session (ALLOW_NO_AUTH mode) must not raise


def test_rate_limit_blocks_after_threshold():
    from app.auth import LOGIN_RATE_LIMIT, check_rate_limit, record_login_attempt

    key = "rate-limit-test-client"
    for _ in range(LOGIN_RATE_LIMIT):
        assert check_rate_limit(key) is True
        record_login_attempt(key)
    assert check_rate_limit(key) is False
