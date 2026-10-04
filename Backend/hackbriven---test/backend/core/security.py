from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from backend.config import settings

_PBKDF2_ROUNDS = 200_000

_secret_lock = threading.Lock()
_secret_cache: bytes | None = None


def _secret() -> bytes:
    """Signing key for session tokens and media links. SESSION_SECRET wins;
    otherwise a random key is generated once and persisted next to the job
    storage so tokens survive a process restart on a normal disk."""
    global _secret_cache
    if _secret_cache is not None:
        return _secret_cache
    with _secret_lock:
        if _secret_cache is not None:
            return _secret_cache
        if settings.session_secret:
            _secret_cache = settings.session_secret.encode("utf-8")
            return _secret_cache
        path = settings.storage_path / ".session_secret"
        if path.exists():
            data = path.read_bytes().strip()
        else:
            data = secrets.token_hex(32).encode("ascii")
            path.write_bytes(data)
        _secret_cache = data
        return _secret_cache


def reset_secret_cache() -> None:
    """Test hook: forget the cached key so a changed storage dir/secret is re-read."""
    global _secret_cache
    _secret_cache = None


# --- passwords ---


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"pbkdf2${_PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt, expected = stored.split("$")
        if scheme != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(rounds))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


# A real hash to compare against when the email is unknown, so "no such user"
# and "wrong password" take the same time.
DUMMY_HASH = hash_password("not-a-real-password")


# --- session tokens: base64url(email|expiry).hmac ---


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()


def issue_token(email: str, *, ttl_hours: int | None = None) -> str:
    ttl = settings.session_ttl_hours if ttl_hours is None else ttl_hours
    expires = int(time.time() + ttl * 3600)
    payload = _b64(f"{email}|{expires}".encode("utf-8"))
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> str | None:
    """Return the email a valid, unexpired session token was issued to, else None."""
    try:
        payload, signature = token.split(".", 1)
        if not hmac.compare_digest(_sign(payload), signature):
            return None
        email, expires = _unb64(payload).decode("utf-8").rsplit("|", 1)
        if int(expires) < time.time():
            return None
        return email
    except (ValueError, TypeError, UnicodeError):
        return None


# --- media links: <video>/<img> tags can't send an Authorization header ---


def media_sig(job_id: str) -> str:
    return hmac.new(_secret(), f"media:{job_id}".encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def verify_media_sig(job_id: str, sig: str | None) -> bool:
    return bool(sig) and hmac.compare_digest(media_sig(job_id), sig)


# --- tiny in-memory sliding-window limiter (login/register/boost) ---

_rate_lock = threading.Lock()
_rate_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limited(key: str, *, limit: int, window_seconds: float) -> bool:
    """Record one hit for `key`; True means the caller is over the limit."""
    now = time.monotonic()
    with _rate_lock:
        hits = _rate_hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return True
        hits.append(now)
        return False


def reset_rate_limits() -> None:
    with _rate_lock:
        _rate_hits.clear()
