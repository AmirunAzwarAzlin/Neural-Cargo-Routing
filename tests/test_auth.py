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
