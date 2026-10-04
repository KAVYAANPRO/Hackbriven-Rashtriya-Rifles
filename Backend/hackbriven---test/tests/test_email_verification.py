from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.config import settings
from backend.core import credits, docstore, users
from backend.services import mailer


@pytest.fixture
def outbox(monkeypatch):
    """Turn verification on and capture outgoing mail instead of sending it."""
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_user", "noreply@example.com")
    monkeypatch.setattr(settings, "email_verification", "auto")
    sent: list[dict] = []
    with patch("backend.api.routes.mailer.send", side_effect=lambda to, subject, text, html: sent.append(
        {"to": to, "subject": subject, "text": text, "html": html}
    )):
        yield sent


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _code(mail: dict) -> str:
    return re.search(r"\b(\d{6})\b", mail["text"]).group(1)


def _register(client, email="new@example.com"):
    return client.post("/auth/register", json={"email": email, "password": "secret1"})


def test_register_sends_a_code_and_gives_no_session_or_credits_yet(client, outbox) -> None:
    response = _register(client)
    assert response.status_code == 200
    body = response.json()
    assert body["verification_required"] is True
    assert "token" not in body
    assert outbox[0]["to"] == "new@example.com"
    assert _code(outbox[0]) in outbox[0]["subject"]
    assert credits.get_balance("new@example.com") == 0
    stored = docstore.get("users", "new@example.com")
    assert _code(outbox[0]) not in str(stored)  # only a keyed hash of the code is stored


def test_correct_code_verifies_signs_in_grants_credits_and_welcomes(client, outbox) -> None:
    _register(client)
    response = client.post("/auth/verify-email", json={"email": "New@Example.com", "code": _code(outbox[0])})
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["email_verified"] is True
    assert body["user"]["balance"] == settings.signup_credits
    assert outbox[-1]["subject"] == "Welcome to IdeaFeed AI"
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {body['token']}"}).status_code == 200


def test_unverified_account_cannot_sign_in(client, outbox) -> None:
    _register(client)
    response = client.post("/auth/login", json={"email": "new@example.com", "password": "secret1"})
    assert response.status_code == 403
    assert response.json()["detail"]["verification_required"] is True


def test_wrong_codes_are_counted_and_then_locked(client, outbox) -> None:
    _register(client)
    real = _code(outbox[0])
    wrong = "000000" if real != "000000" else "111111"
    for left in (4, 3, 2, 1, 0):
        r = client.post("/auth/verify-email", json={"email": "new@example.com", "code": wrong})
        assert r.status_code == 400
        assert f"({left} " in r.json()["detail"]
    locked = client.post("/auth/verify-email", json={"email": "new@example.com", "code": real})
    assert locked.status_code == 429  # even the right code is refused once the guesses are used up


def test_expired_code_is_refused(client, outbox) -> None:
    _register(client)
    user = docstore.get("users", "new@example.com")
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    docstore.update("users", "new@example.com", {"verification": {**user["verification"], "expires_at": past}})
    r = client.post("/auth/verify-email", json={"email": "new@example.com", "code": _code(outbox[0])})
    assert r.status_code == 410


def test_resend_replaces_the_code_and_is_rate_limited(client, outbox) -> None:
    _register(client)
    first = _code(outbox[0])
    r = client.post("/auth/resend-code", json={"email": "new@example.com"})
    assert r.status_code == 200 and len(outbox) == 2
    second = _code(outbox[1])
    if first != second:
        assert client.post("/auth/verify-email", json={"email": "new@example.com", "code": first}).status_code == 400
    assert client.post("/auth/resend-code", json={"email": "new@example.com"}).status_code == 429
    assert client.post("/auth/verify-email", json={"email": "new@example.com", "code": second}).status_code == 200


def test_resend_does_not_reveal_whether_an_account_exists(client, outbox) -> None:
    r = client.post("/auth/resend-code", json={"email": "nobody@example.com"})
    assert r.status_code == 200 and r.json()["sent"] is True
    assert outbox == []


def test_registering_again_while_unverified_points_back_to_the_code(client, outbox) -> None:
    _register(client)
    again = _register(client)
    assert again.status_code == 409
    assert again.json()["detail"]["verification_required"] is True


def test_failed_email_send_rolls_the_account_back(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_user", "noreply@example.com")
    with patch("backend.api.routes.mailer.send", side_effect=mailer.MailError("down")):
        r = _register(client)
    assert r.status_code == 503
    assert users.get("new@example.com") is None  # free to try again


def test_existing_accounts_without_the_flag_keep_working(client, outbox) -> None:
    docstore.insert("users", "old@example.com", {
        "email": "old@example.com", "password_hash": users.security.hash_password("secret1"),
        "plan": "free", "plan_expires_at": None, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    assert client.post("/auth/login", json={"email": "old@example.com", "password": "secret1"}).status_code == 200


def test_without_smtp_registration_works_as_before(client) -> None:
    assert not settings.smtp_configured
    body = _register(client).json()
    assert body["token"] and body["user"]["balance"] == settings.signup_credits


def test_verification_email_contains_the_code_and_expiry() -> None:
    subject, text, html = mailer.verification_email("123456", 15)
    assert "123456" in subject and "123456" in text and "123456" in html
    assert "15 minutes" in text


def test_mailer_uses_starttls_and_logs_in(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_security", "starttls")
    monkeypatch.setattr(settings, "smtp_user", "me@gmail.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password")
    with patch("backend.services.mailer.smtplib.SMTP") as smtp_cls:
        smtp = smtp_cls.return_value.__enter__.return_value
        mailer.send("to@example.com", "s", "t", "<p>h</p>")
    smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=20)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("me@gmail.com", "app-password")
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "to@example.com" and "IdeaFeed AI" in message["From"]
