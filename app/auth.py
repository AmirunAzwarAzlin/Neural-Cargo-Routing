import base64
import hashlib
import hmac
import time

from fastapi import Cookie, HTTPException, status

from config import settings

COOKIE_NAME = "sdoc_session"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60  # 8 hours

LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW_SECONDS = 60.0
# In-memory, single-process only: a multi-instance deployment needs a shared
# store (e.g. Redis) for this to rate-limit across instances.
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}


def check_password(password: str) -> bool:
    return hmac.compare_digest(password.encode("utf-8"), settings.dashboard_password.encode("utf-8"))


def _session_secret() -> bytes | None:
    if not settings.session_secret:
        return None
    return settings.session_secret.encode("utf-8")


def _sign(payload: bytes) -> str:
    secret = _session_secret()
    if secret is None:
        raise RuntimeError("SESSION_SECRET is not configured")
    sig = hmac.new(secret, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")


def make_session_token(reviewer_name: str = "reviewer") -> str:
    """A random, HMAC-signed, expiring session token — independent of the
    password, so a leaked cookie doesn't leak (or even relate to) the
    password, and can't be forged without SESSION_SECRET.

    Carries the reviewer's name (base64url-encoded, tamper-proof via the
    same signature) so audit rows can record who acted instead of a
    hardcoded "human_reviewer" string.
    """
    issued_at = str(int(time.time()))
    name_b64 = base64.urlsafe_b64encode(reviewer_name.encode("utf-8")).decode("ascii").rstrip("=")
    payload = f"{issued_at}:{name_b64}"
    return f"{payload}.{_sign(payload.encode('ascii'))}"


def _split_session_token(token: str) -> tuple[str, str] | None:
    """Returns (issued_at_str, name_b64) if the signature is valid, else None."""
    if not token or _session_secret() is None:
        return None
    payload, sep, sig = token.rpartition(".")
    if not sep:
        return None
    expected_sig = _sign(payload.encode("ascii", errors="replace"))
    if not hmac.compare_digest(sig.encode("ascii", errors="replace"), expected_sig.encode("ascii")):
        return None
    issued_at_str, colon, name_b64 = payload.partition(":")
    if not colon:
        return None
    return issued_at_str, name_b64


def _verify_session_token(token: str | None) -> bool:
    if not token:
        return False
    split = _split_session_token(token)
    if split is None:
        return False
    issued_at_str, _ = split
    try:
        issued_at = int(issued_at_str)
    except ValueError:
        return False
    return 0 <= (time.time() - issued_at) <= SESSION_MAX_AGE_SECONDS


def reviewer_name_from_session(session_token: str) -> str:
    """The reviewer name carried in a valid session token, for use as the
    audit trail's `actor`. Falls back to a generic label rather than
    raising, since callers may hold an already-verified session string."""
    split = _split_session_token(session_token) if session_token else None
    if split is None:
        return "reviewer"
    _, name_b64 = split
    padding = "=" * (-len(name_b64) % 4)
    try:
        return base64.urlsafe_b64decode(name_b64 + padding).decode("utf-8")
    except Exception:
        return "reviewer"


def csrf_token_for_session(session_token: str) -> str:
    """A stateless CSRF token bound to the session: verifiable without
    server-side storage, unforgeable without SESSION_SECRET."""
    return _sign(f"csrf:{session_token}".encode("utf-8"))


def check_rate_limit(client_key: str) -> bool:
    """True if client_key is within the allowed login-attempt rate."""
    now = time.time()
    attempts = [t for t in _LOGIN_ATTEMPTS.get(client_key, []) if now - t < LOGIN_RATE_WINDOW_SECONDS]
    _LOGIN_ATTEMPTS[client_key] = attempts
    return len(attempts) < LOGIN_RATE_LIMIT


def record_login_attempt(client_key: str) -> None:
    _LOGIN_ATTEMPTS.setdefault(client_key, []).append(time.time())


def require_auth(sdoc_session: str | None = Cookie(default=None)) -> str:
    if not settings.dashboard_password:
        if settings.allow_no_auth:
            return ""  # explicit dev-only opt-in; no session, no CSRF binding
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DASHBOARD_PASSWORD is not set")
    if not _verify_session_token(sdoc_session):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return sdoc_session


def require_csrf(csrf_token: str, session: str) -> None:
    if not session:
        return  # ALLOW_NO_AUTH dev mode: no session to bind a CSRF token to
    expected = csrf_token_for_session(session)
    if not csrf_token or not hmac.compare_digest(csrf_token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid or missing CSRF token")
