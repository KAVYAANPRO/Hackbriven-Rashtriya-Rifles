"""POST /auth/clerk: Clerk ("Continue with Google") session token -> app session. No network:
JWTs are signed with a throwaway RSA key and the JWKS fetch + Clerk Backend API are mocked."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.config import settings
from backend.core import security, users
from backend.services import clerk_auth

ISSUER = "https://example-app.clerk.accounts.dev"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def clerk_on(monkeypatch):
    monkeypatch.setattr(settings, "clerk_issuer", ISSUER)
    monkeypatch.setattr(settings, "clerk_jwks_url", "")
    monkeypatch.setattr(settings, "clerk_publishable_key", "")
    monkeypatch.setattr(settings, "clerk_secret_key", "sk_test_dummy")
    monkeypatch.setattr(settings, "clerk_authorized_parties", "")
    fake = SimpleNamespace(get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=_KEY.public_key()))
    with patch.object(clerk_auth, "_jwk_client", return_value=fake):
        yield


@pytest.fixture
def clerk_off(monkeypatch):
    for name in ("clerk_issuer", "clerk_jwks_url", "clerk_publishable_key", "clerk_secret_key"):
        monkeypatch.setattr(settings, name, "")


def _token(sub="user_123", key=_KEY, iss=ISSUER, exp_in=60, **extra) -> str:
    now = int(time.time())
    claims = {"sub": sub, "iss": iss, "iat": now, "nbf": now, "exp": now + exp_in, "sid": "sess_1", **extra}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "ins_1"})


def _clerk_user(email="g@example.com", status="verified"):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "id": "user_123",
        "primary_email_address_id": "idn_1",
        "email_addresses": [
            {"id": "idn_0", "email_address": "other@example.com", "verification": {"status": "verified"}},
            {"id": "idn_1", "email_address": email, "verification": {"status": status}},
        ],
    }
    return resp


def test_returns_503_when_clerk_not_configured(client, clerk_off) -> None:
    r = client.post("/auth/clerk", json={"token": "a.b.c"})
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]


def test_creates_verified_account_with_login_shape(client, clerk_on) -> None:
    with patch("backend.services.clerk_auth.httpx.get", return_value=_clerk_user("G@Example.com")) as get:
        r = client.post("/auth/clerk", json={"token": _token()})
    assert r.status_code == 200, r.text
    body = r.json()
    assert get.call_args.args[0].endswith("/users/user_123")
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer sk_test_dummy"
    assert body["authenticated"] is True and "auth_required" in body
    assert security.verify_token(body["token"]) == "g@example.com"
    assert body["user"]["email"] == "g@example.com"
    assert body["user"]["email_verified"] is True
    assert body["user"]["balance"] == settings.signup_credits
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200 and me.json()["email"] == "g@example.com"


def test_existing_account_signs_in_without_extra_credits(client, clerk_on) -> None:
    reg = client.post("/auth/register", json={"email": "g@example.com", "password": "secret1"})
    assert reg.status_code == 200
    with patch("backend.services.clerk_auth.httpx.get", return_value=_clerk_user()):
        r = client.post("/auth/clerk", json={"token": _token()})
    assert r.status_code == 200
    assert r.json()["user"]["balance"] == settings.signup_credits  # bonus not granted twice
    # Password login still works for that account.
    assert client.post("/auth/login", json={"email": "g@example.com", "password": "secret1"}).status_code == 200


def test_unverified_signup_is_verified_and_its_password_revoked(client, clerk_on) -> None:
    users.register("g@example.com", "attacker1", verified=False)
    with patch("backend.services.clerk_auth.httpx.get", return_value=_clerk_user()):
        r = client.post("/auth/clerk", json={"token": _token()})
    assert r.status_code == 200
    assert r.json()["user"]["email_verified"] is True
    assert r.json()["user"]["balance"] == settings.signup_credits
    assert client.post("/auth/login", json={"email": "g@example.com", "password": "attacker1"}).status_code == 401


def test_verified_email_claim_skips_backend_api(client, clerk_on) -> None:
    with patch("backend.services.clerk_auth.httpx.get") as get:
        r = client.post("/auth/clerk", json={"token": _token(email="claim@example.com", email_verified=True)})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "claim@example.com"
    get.assert_not_called()


def test_unverified_clerk_email_is_rejected(client, clerk_on) -> None:
    resp = _clerk_user(status="unverified")
    resp.json.return_value["email_addresses"] = resp.json.return_value["email_addresses"][1:]
    with patch("backend.services.clerk_auth.httpx.get", return_value=resp):
        r = client.post("/auth/clerk", json={"token": _token()})
    assert r.status_code == 403


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        _token(key=_OTHER_KEY),  # wrong signature
        _token(iss="https://evil.example.com"),  # issuer must be ours, not the token's
        _token(exp_in=-120),  # expired
    ],
)
def test_bad_tokens_are_rejected(client, clerk_on, token) -> None:
    with patch("backend.services.clerk_auth.httpx.get", return_value=_clerk_user()) as get:
        r = client.post("/auth/clerk", json={"token": token})
    assert r.status_code == 401
    get.assert_not_called()
    assert users.get("g@example.com") is None


def test_authorized_parties_enforced(client, clerk_on, monkeypatch) -> None:
    monkeypatch.setattr(settings, "clerk_authorized_parties", "http://localhost:5173")
    with patch("backend.services.clerk_auth.httpx.get", return_value=_clerk_user()):
        bad = client.post("/auth/clerk", json={"token": _token(azp="https://evil.example.com")})
        ok = client.post("/auth/clerk", json={"token": _token(azp="http://localhost:5173")})
    assert bad.status_code == 401
    assert ok.status_code == 200


def test_missing_secret_key_is_503_when_email_needs_lookup(client, clerk_on, monkeypatch) -> None:
    monkeypatch.setattr(settings, "clerk_secret_key", "")
    r = client.post("/auth/clerk", json={"token": _token()})
    assert r.status_code == 503


def test_issuer_derived_from_publishable_key(monkeypatch) -> None:
    import base64

    monkeypatch.setattr(settings, "clerk_issuer", "")
    monkeypatch.setattr(settings, "clerk_jwks_url", "")
    pk = "pk_test_" + base64.b64encode(b"example-app.clerk.accounts.dev$").decode()
    monkeypatch.setattr(settings, "clerk_publishable_key", pk)
    assert settings.clerk_issuer_url == ISSUER
    assert settings.clerk_jwks == ISSUER + "/.well-known/jwks.json"
    assert settings.has_clerk
