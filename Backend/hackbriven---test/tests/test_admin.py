from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.config import settings


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "admin_emails", "boss@example.com")
    return TestClient(create_app())


def _token(client, email) -> dict:
    body = client.post("/auth/register", json={"email": email, "password": "secret1"}).json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]


def test_admin_flag_is_on_the_profile(client) -> None:
    _, boss = _token(client, "Boss@Example.com")
    _, other = _token(client, "user@example.com")
    assert boss["is_admin"] is True
    assert other["is_admin"] is False


def test_only_the_admin_can_open_the_orchestra_endpoint(client) -> None:
    boss, _ = _token(client, "boss@example.com")
    user, _ = _token(client, "user@example.com")
    assert client.get("/admin/providers").status_code == 403
    assert client.get("/admin/providers", headers=user).status_code == 403
    response = client.get("/admin/providers", headers=boss)
    assert response.status_code == 200
    body = response.json()
    assert "key_pool_size" in body["motion"]
    assert isinstance(body["image"]["cloudflare_accounts"], list)


def test_public_status_hides_operational_detail(client) -> None:
    body = client.get("/providers/status").json()
    assert "key_pool_size" not in body["motion"]
    assert "cloudflare_accounts" not in body["image"]
    assert body["script"]["chain"]  # still enough for the app to work


def test_cloudflare_tokens_never_appear_in_admin_output(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "cloudflare_account_id", "acct00001111")
    monkeypatch.setattr(settings, "cloudflare_api_token", "very-secret-token")
    monkeypatch.setattr(settings, "cloudflare_accounts", "acct22223333:another-secret")
    boss, _ = _token(client, "boss@example.com")
    text = client.get("/admin/providers", headers=boss).text
    assert "very-secret-token" not in text and "another-secret" not in text
    assert "acct00001111" not in text  # ids are masked to their last 4 characters
    accounts = client.get("/admin/providers", headers=boss).json()["image"]["cloudflare_accounts"]
    assert [a["account"] for a in accounts] == ["...1111", "...3333"]


def test_account_pool_parsing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "cloudflare_account_id", "a1")
    monkeypatch.setattr(settings, "cloudflare_api_token", "t1")
    monkeypatch.setattr(settings, "cloudflare_accounts", " a2:t2, bad-entry ,a1:t1, a2:t2b, a3:t3 ")
    # exact duplicates dropped; a second token for the same account is kept as a backup key
    assert settings.cloudflare_account_pool == [("a1", "t1"), ("a2", "t2"), ("a2", "t2b"), ("a3", "t3")]


def test_keys_on_one_account_share_its_allowance(monkeypatch) -> None:
    from backend.services import image_generator

    monkeypatch.setattr(settings, "cloudflare_account_id", "acct1111")
    monkeypatch.setattr(settings, "cloudflare_api_token", "t1")
    monkeypatch.setattr(settings, "cloudflare_accounts", "acct2222:t2,acct2222:t3")
    image_generator._mark_quota_exhausted("acct2222")
    status = image_generator.cloudflare_account_status()
    assert [(s["account"], s["key"], s["available"]) for s in status] == [
        ("...1111", 1, True), ("...2222", 1, False), ("...2222", 2, False)]
    assert image_generator.cloudflare_quota_exhausted_until() is None  # acct1111 still has allowance
