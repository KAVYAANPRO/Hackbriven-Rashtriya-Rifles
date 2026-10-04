from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.config import settings
from backend.core import credits, docstore, orders, security, users
from backend.models.schemas import MotionTier


@pytest.fixture
def client() -> TestClient:
    from backend.api.routes import job_manager

    job_manager._jobs.clear()  # the job store is a process-wide singleton
    return TestClient(create_app())


def _register(client: TestClient, email: str = "a@example.com", password: str = "secret1") -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_job(client: TestClient, token: str, tier: str = "basic", **extra) -> "tuple[int, dict]":
    with patch("backend.api.routes.run_pipeline"):
        response = client.post("/jobs", json={"topic": "a topic", "motion_tier": tier, **extra}, headers=_auth(token))
    return response.status_code, response.json()


# --- registration / login ---


def test_register_returns_token_profile_and_signup_credits(client) -> None:
    body = _register(client)
    assert body["user"]["email"] == "a@example.com"
    assert body["user"]["plan"] == "free"
    assert body["user"]["balance"] == settings.signup_credits
    assert security.verify_token(body["token"]) == "a@example.com"


def test_register_normalises_email_and_rejects_duplicates(client) -> None:
    _register(client, "Mixed@Example.com")
    again = client.post("/auth/register", json={"email": "mixed@example.COM", "password": "secret1"})
    assert again.status_code == 409


@pytest.mark.parametrize(
    "email,password",
    [("not-an-email", "secret1"), ("a@b", "secret1"), ("ok@example.com", "123")],
)
def test_register_validates_input(client, email, password) -> None:
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 422


def test_login_with_correct_and_wrong_password(client) -> None:
    _register(client)
    ok = client.post("/auth/login", json={"email": "a@example.com", "password": "secret1"})
    assert ok.status_code == 200
    assert ok.json()["authenticated"] is True
    assert security.verify_token(ok.json()["token"]) == "a@example.com"

    assert client.post("/auth/login", json={"email": "a@example.com", "password": "nope"}).status_code == 401
    assert client.post("/auth/login", json={"email": "ghost@example.com", "password": "secret1"}).status_code == 401


def test_login_is_rate_limited(client) -> None:
    _register(client)
    statuses = [
        client.post("/auth/login", json={"email": "a@example.com", "password": "bad"}).status_code for _ in range(12)
    ]
    assert statuses[:10] == [401] * 10
    assert 429 in statuses[10:]


def test_me_requires_a_valid_token(client) -> None:
    token = _register(client)["token"]
    assert client.get("/auth/me", headers=_auth(token)).json()["email"] == "a@example.com"
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=_auth(token + "x")).status_code == 401


def test_password_is_not_stored_in_plain_text(client) -> None:
    _register(client, password="hunter22")
    stored = docstore.get("users", "a@example.com")
    assert "hunter22" not in str(stored)
    assert stored["password_hash"].startswith("pbkdf2$")


def test_tokens_expire() -> None:
    expired = security.issue_token("a@example.com", ttl_hours=-1)
    assert security.verify_token(expired) is None


# --- job ownership and per-account credits ---


def test_job_charges_only_the_callers_account(client) -> None:
    token = _register(client)["token"]
    status, job = _make_job(client, token, "basic")
    assert status == 200
    assert job["owner"] == "a@example.com"
    assert credits.get_balance("a@example.com") == settings.signup_credits - credits.cost_for_tier(MotionTier.BASIC)
    assert credits.get_balance() == 0  # the default account is untouched


def test_jobs_are_private_to_their_owner(client) -> None:
    token_a = _register(client, "a@example.com")["token"]
    token_b = _register(client, "b@example.com")["token"]
    _, job = _make_job(client, token_a)

    assert [j["id"] for j in client.get("/jobs", headers=_auth(token_a)).json()] == [job["id"]]
    assert client.get("/jobs", headers=_auth(token_b)).json() == []
    assert client.get("/jobs").json() == []  # anonymous caller is another account too

    assert client.get(f"/jobs/{job['id']}", headers=_auth(token_b)).status_code == 404
    assert client.get(f"/jobs/{job['id']}").status_code == 404
    assert client.post(f"/jobs/{job['id']}/cancel", headers=_auth(token_b)).status_code == 404
    assert client.get(f"/jobs/{job['id']}/quality-report", headers=_auth(token_b)).status_code == 404

    assert client.get("/analytics/overview", headers=_auth(token_a)).json()["total_jobs"] == 1
    assert client.get("/analytics/overview", headers=_auth(token_b)).json()["total_jobs"] == 0


def test_analytics_reports_status_tier_and_language_breakdowns(client) -> None:
    token = _register(client)["token"]
    _make_job(client, token, "basic", language="hi")
    _make_job(client, token, "basic", language="en")
    body = client.get("/analytics/overview", headers=_auth(token)).json()
    assert body["by_status"] == {"queued": 2}
    assert body["by_tier"] == {"basic": 2}
    assert body["by_language"] == {"hi": 1, "en": 1}


def test_idempotency_key_is_scoped_per_account(client) -> None:
    token_a = _register(client, "a@example.com")["token"]
    token_b = _register(client, "b@example.com")["token"]
    headers_a = {**_auth(token_a), "Idempotency-Key": "same-key"}
    headers_b = {**_auth(token_b), "Idempotency-Key": "same-key"}
    with patch("backend.api.routes.run_pipeline"):
        first = client.post("/jobs", json={"topic": "t", "motion_tier": "basic"}, headers=headers_a).json()
        repeat = client.post("/jobs", json={"topic": "t", "motion_tier": "basic"}, headers=headers_a).json()
        other = client.post("/jobs", json={"topic": "t", "motion_tier": "basic"}, headers=headers_b).json()
    assert first["id"] == repeat["id"]
    assert other["id"] != first["id"]
    assert credits.get_balance("a@example.com") == settings.signup_credits - 1  # charged once


def test_insufficient_credits_returns_402_with_details(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "signup_credits", 0)
    token = _register(client)["token"]
    status, body = _make_job(client, token, "basic")
    assert status == 402
    assert body["detail"]["required"] == credits.cost_for_tier(MotionTier.BASIC)
    assert body["detail"]["available"] == 0
    assert body["detail"]["top_up"] == "/credits/create-order"


# --- plans and tier gating ---


def test_free_plan_cannot_use_paid_tiers_and_is_not_charged(client) -> None:
    token = _register(client)["token"]
    status, body = _make_job(client, token, "balanced")
    assert status == 403
    assert body["detail"]["required_plan"] == "pro"
    assert body["detail"]["plan"] == "free"
    assert credits.get_balance("a@example.com") == settings.signup_credits


def test_paid_plan_unlocks_every_tier(client) -> None:
    token = _register(client)["token"]
    users.activate_plan("a@example.com", "pro")
    assert _make_job(client, token, "max")[0] == 200
    assert _make_job(client, token, "balanced")[0] == 200


def test_lapsed_paid_plan_falls_back_to_free(client) -> None:
    token = _register(client)["token"]
    users.activate_plan("a@example.com", "pro")
    docstore.update("users", "a@example.com", {"plan_expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()})

    me = client.get("/auth/me", headers=_auth(token)).json()
    assert me["plan"] == "free"
    assert me["plan_expires_at"] is None
    assert _make_job(client, token, "balanced")[0] == 403


def test_renewing_the_same_plan_extends_from_the_current_expiry(client) -> None:
    _register(client)
    first = users.activate_plan("a@example.com", "pro")
    second = users.activate_plan("a@example.com", "pro")
    gap = datetime.fromisoformat(second["plan_expires_at"]) - datetime.fromisoformat(first["plan_expires_at"])
    assert gap == timedelta(days=30)


def test_plans_endpoint_is_public_and_complete(client) -> None:
    body = client.get("/plans").json()
    assert set(body["cost_by_tier"]) == {"basic", "balanced", "max"}
    assert [p["id"] for p in body["plans"]] == ["free", "pro", "studio"]
    assert next(p for p in body["plans"] if p["id"] == "free")["tiers"] == ["basic"]
    assert [p["id"] for p in body["packs"]] == [0, 1, 2]
    assert body["payments"] == {"razorpay_configured": settings.has_razorpay}


def test_credits_endpoint_reports_plan_and_allowed_tiers(client) -> None:
    token = _register(client)["token"]
    body = client.get("/credits", headers=_auth(token)).json()
    assert body["balance"] == settings.signup_credits
    assert body["plan"] == "free"
    assert body["tiers_allowed"] == ["basic"]
    assert len(body["packs"]) == 3


# --- payment orders: signature alone is never enough, and an order redeems once ---


def _fake_order(order_id: str = "order_X") -> dict:
    return {"order_id": order_id, "amount": 0, "currency": "INR", "key_id": "rzp_test_x", "credits": 0}


def _buy(client, token, body, order_id="order_1", payment_id="pay_1"):
    with patch("backend.api.routes.payments.create_order", return_value=_fake_order(order_id)):
        created = client.post("/credits/create-order", json=body, headers=_auth(token))
    assert created.status_code == 200, created.text
    with patch("backend.api.routes.payments.verify_payment_signature"):
        return created.json(), client.post(
            "/credits/verify-payment",
            json={"razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": "sig"},
            headers=_auth(token),
        )


def test_buying_a_pack_credits_the_account_exactly_once(client) -> None:
    token = _register(client)["token"]
    created, verified = _buy(client, token, {"pack": 1})
    assert created["kind"] == "pack"
    assert verified.status_code == 200
    assert verified.json()["credits_added"] == 60
    assert verified.json()["already_processed"] is False
    assert credits.get_balance("a@example.com") == settings.signup_credits + 60

    with patch("backend.api.routes.payments.verify_payment_signature"):
        replay = client.post(
            "/credits/verify-payment",
            json={"razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1", "razorpay_signature": "sig"},
            headers=_auth(token),
        )
    assert replay.status_code == 200
    assert replay.json()["already_processed"] is True
    assert replay.json()["credits_added"] == 0
    assert credits.get_balance("a@example.com") == settings.signup_credits + 60  # not credited twice


def test_create_order_prices_the_order_from_the_server_side_pack(client) -> None:
    token = _register(client)["token"]
    with patch("backend.api.routes.payments.create_order", return_value=_fake_order()) as mock_create:
        client.post("/credits/create-order", json={"pack": 2}, headers=_auth(token))
    kwargs = mock_create.call_args.kwargs
    assert kwargs["amount_paise"] == 99900
    assert kwargs["credits"] == 150


def test_buying_a_plan_activates_it_and_grants_its_credits(client) -> None:
    token = _register(client)["token"]
    created, verified = _buy(client, token, {"plan": "pro"})
    body = verified.json()
    assert created["kind"] == "plan" and created["plan"] == "pro"
    assert body["plan"] == "pro"
    assert body["plan_expires_at"]
    assert body["credits_added"] == 120
    assert client.get("/auth/me", headers=_auth(token)).json()["plan"] == "pro"
    assert _make_job(client, token, "max")[0] == 200


def test_another_account_cannot_redeem_my_order(client) -> None:
    token_a = _register(client, "a@example.com")["token"]
    token_b = _register(client, "b@example.com")["token"]
    with patch("backend.api.routes.payments.create_order", return_value=_fake_order("order_A")):
        client.post("/credits/create-order", json={"pack": 0}, headers=_auth(token_a))
    with patch("backend.api.routes.payments.verify_payment_signature"):
        stolen = client.post(
            "/credits/verify-payment",
            json={"razorpay_order_id": "order_A", "razorpay_payment_id": "pay", "razorpay_signature": "s"},
            headers=_auth(token_b),
        )
    assert stolen.status_code == 404
    assert credits.get_balance("b@example.com") == settings.signup_credits


def test_valid_signature_for_an_unknown_order_is_rejected(client) -> None:
    token = _register(client)["token"]
    with patch("backend.api.routes.payments.verify_payment_signature"):
        response = client.post(
            "/credits/verify-payment",
            json={"razorpay_order_id": "never_created", "razorpay_payment_id": "p", "razorpay_signature": "s"},
            headers=_auth(token),
        )
    assert response.status_code == 404


def test_failed_grant_releases_the_order_so_the_buyer_can_retry(client) -> None:
    token = _register(client)["token"]
    with patch("backend.api.routes.payments.create_order", return_value=_fake_order("order_R")):
        client.post("/credits/create-order", json={"pack": 0}, headers=_auth(token))
    body = {"razorpay_order_id": "order_R", "razorpay_payment_id": "pay_R", "razorpay_signature": "s"}
    with patch("backend.api.routes.payments.verify_payment_signature"):
        with patch("backend.api.routes.credits.add_credits", side_effect=RuntimeError("db down")):
            assert client.post("/credits/verify-payment", json=body, headers=_auth(token)).status_code == 500
        assert orders.get("order_R")["status"] == "pending"
        retry = client.post("/credits/verify-payment", json=body, headers=_auth(token))
    assert retry.status_code == 200
    assert retry.json()["credits_added"] == 20


def test_create_order_validation(client) -> None:
    token = _register(client)["token"]
    assert client.post("/credits/create-order", json={"pack": 99}, headers=_auth(token)).status_code == 422
    assert client.post("/credits/create-order", json={"plan": "free"}, headers=_auth(token)).status_code == 422
    assert client.post("/credits/create-order", json={"plan": "nope"}, headers=_auth(token)).status_code == 422
    assert client.post("/credits/create-order", json={"plan": "pro", "pack": 0}, headers=_auth(token)).status_code == 422
    # plans belong to accounts, so an anonymous caller can't buy one
    assert client.post("/credits/create-order", json={"plan": "pro"}).status_code == 401


# --- auth modes ---


def test_require_login_locks_anonymous_callers_out(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "require_login", True)
    assert client.post("/jobs", json={"topic": "t"}).status_code == 401
    assert client.get("/jobs").status_code == 401
    assert client.get("/credits").status_code == 401
    token = _register(client)["token"]
    assert client.get("/jobs", headers=_auth(token)).status_code == 200


def test_legacy_api_key_still_works_and_acts_as_the_default_account(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "backend_api_key", "service-secret")
    credits.add_credits(10, reason="seed")  # default account
    with patch("backend.api.routes.run_pipeline"):
        denied = client.post("/jobs", json={"topic": "t", "motion_tier": "basic"})
        allowed = client.post(
            "/jobs", json={"topic": "t", "motion_tier": "basic"}, headers=_auth("service-secret")
        )
    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["owner"] is None
    assert credits.get_balance() == 10 - credits.cost_for_tier(MotionTier.BASIC)


def test_user_token_is_accepted_when_the_legacy_key_is_enabled(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "backend_api_key", "service-secret")
    token = _register(client)["token"]
    assert _make_job(client, token, "basic")[0] == 200


def test_legacy_login_response_shape_is_unchanged(client, monkeypatch) -> None:
    assert client.post("/auth/login", json={"api_key": ""}).json() == {"authenticated": True, "auth_required": False}
    monkeypatch.setattr(settings, "backend_api_key", "service-secret")
    assert client.post("/auth/login", json={"api_key": "service-secret"}).json() == {
        "authenticated": True,
        "auth_required": True,
    }
    assert client.post("/auth/login", json={"api_key": "wrong"}).status_code == 401


# --- misc ---


def test_cors_allows_the_configured_frontend_origin(client) -> None:
    response = client.options(
        "/jobs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,idempotency-key,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()

    foreign = client.options(
        "/jobs", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in foreign.headers


def test_ledger_migration_assigns_legacy_rows_to_the_default_account(tmp_path) -> None:
    import sqlite3

    db = settings.storage_path / "credits.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, delta INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')))")
    conn.execute("INSERT INTO ledger (delta, reason) VALUES (25, 'old row')")
    conn.commit()
    conn.close()

    assert credits.get_balance() == 25
    assert credits.get_balance("someone@example.com") == 0
