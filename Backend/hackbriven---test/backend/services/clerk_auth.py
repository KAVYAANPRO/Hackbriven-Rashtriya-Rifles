"""Clerk session-token verification for "Continue with Google".

The browser signs in with Clerk, then sends its short-lived Clerk session JWT to POST /auth/clerk.
We verify it against the Clerk instance's JWKS (RS256, issuer pinned to *our* configured instance,
never taken from the token) and look up the user's verified primary email via the Clerk Backend API.
"""

from __future__ import annotations

import logging
import threading

import httpx
import jwt
from jwt import PyJWKClient

from backend.config import settings

logger = logging.getLogger(__name__)


class ClerkError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


_jwk_lock = threading.Lock()
_jwk_clients: dict[str, PyJWKClient] = {}


def _jwk_client(url: str) -> PyJWKClient:
    with _jwk_lock:
        client = _jwk_clients.get(url)
        if client is None:
            client = PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=10)
            _jwk_clients[url] = client
        return client


def verify_session_token(token: str) -> dict:
    """Return the verified claims of a Clerk session JWT, or raise ClerkError."""
    if not settings.has_clerk:
        raise ClerkError(503, "Google sign-in is not configured on this server")
    if not token or token.count(".") != 2:
        raise ClerkError(401, "missing or malformed Clerk session token")
    try:
        signing_key = _jwk_client(settings.clerk_jwks).get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError as exc:
        logger.warning("could not fetch Clerk JWKS: %s", exc)
        raise ClerkError(503, "could not reach Clerk to verify the sign-in - try again") from exc
    except jwt.PyJWTError as exc:
        raise ClerkError(401, "invalid Clerk session token") from exc

    issuer = settings.clerk_issuer_url or None
    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "iat", "sub"], "verify_aud": False},
            leeway=10,
        )
    except jwt.ExpiredSignatureError as exc:
        raise ClerkError(401, "the Clerk session token has expired - sign in again") from exc
    except jwt.PyJWTError as exc:
        raise ClerkError(401, "invalid Clerk session token") from exc

    allowed = settings.clerk_authorized_party_list
    azp = (claims.get("azp") or "").rstrip("/")
    if allowed and azp and azp not in allowed:
        raise ClerkError(401, "this Clerk token was issued for a different site")
    return claims


def _email_from_claims(claims: dict) -> str | None:
    # Only trust an email claim that also says it is verified (a custom session-token template).
    email = claims.get("email") or claims.get("primary_email")
    if email and claims.get("email_verified") is True:
        return str(email)
    return None


def fetch_primary_email(user_id: str) -> str:
    """Look up the user's primary email via the Clerk Backend API; it must be verified."""
    if not settings.clerk_secret_key:
        raise ClerkError(503, "Google sign-in is not fully configured on this server (missing Clerk secret key)")
    try:
        resp = httpx.get(
            f"{settings.clerk_api_url.rstrip('/')}/users/{user_id}",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        logger.warning("Clerk user lookup failed: %s", exc)
        raise ClerkError(503, "could not reach Clerk - try again") from exc
    if resp.status_code == 404:
        raise ClerkError(401, "this Clerk user no longer exists")
    if resp.status_code >= 400:
        logger.warning("Clerk user lookup returned %s", resp.status_code)
        raise ClerkError(503, "Clerk rejected the user lookup - check CLERK_SECRET_KEY")
    data = resp.json()
    addresses = data.get("email_addresses") or []
    primary_id = data.get("primary_email_address_id")
    ordered = sorted(addresses, key=lambda a: a.get("id") != primary_id)  # primary first

    def _verified(addr: dict) -> bool:
        return ((addr.get("verification") or {}).get("status")) == "verified"

    for addr in ordered:
        if addr.get("email_address") and _verified(addr):
            return str(addr["email_address"])
    raise ClerkError(403, "your Clerk account has no verified email address")


def verified_email(token: str) -> str:
    """Verify a Clerk session token and return the signed-in user's verified email."""
    claims = verify_session_token(token)
    return _email_from_claims(claims) or fetch_primary_email(str(claims["sub"]))
