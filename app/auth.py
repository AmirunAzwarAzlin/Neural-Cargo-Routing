import hashlib
import hmac

from fastapi import Cookie, HTTPException, status

from config import settings

COOKIE_NAME = "sdoc_session"


def _expected_token() -> str:
    return hashlib.sha256(settings.dashboard_password.encode()).hexdigest()


def check_password(password: str) -> bool:
    return hmac.compare_digest(password, settings.dashboard_password)


def make_session_token() -> str:
    return _expected_token()


def require_auth(sdoc_session: str | None = Cookie(default=None)) -> None:
    if not settings.dashboard_password:
        if settings.allow_no_auth:
            return  # explicit dev-only opt-in
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DASHBOARD_PASSWORD is not set")
    if sdoc_session != _expected_token():
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
