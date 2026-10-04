from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.credits import InsufficientCreditsError


def _client() -> TestClient:
    return TestClient(create_app())


def test_health() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("backend.api.routes.credits.charge", return_value=4)
@patch("backend.api.routes.run_pipeline")
def test_create_job_returns_queued_job(mock_run_pipeline, mock_charge) -> None:
    client = _client()
    response = client.post("/jobs", json={"topic": "Why EVs are popular"})

    assert response.status_code == 200
    body = response.json()
    assert body["topic"] == "Why EVs are popular"
    assert body["status"] == "queued"
    assert body["motion_tier"] == "balanced"
    assert body["id"]
    mock_charge.assert_called_once()


def test_create_job_rejects_empty_topic() -> None:
    client = _client()
    response = client.post("/jobs", json={"topic": "   "})
    assert response.status_code == 422


@patch("backend.api.routes.credits.charge", side_effect=InsufficientCreditsError(required=4, available=0))
def test_create_job_returns_402_when_credits_insufficient(mock_charge) -> None:
    client = _client()
    response = client.post("/jobs", json={"topic": "topic"})

    assert response.status_code == 402
    body = response.json()["detail"]
    assert body["required"] == 4
    assert body["available"] == 0
    assert body["top_up"] == "/credits/create-order"


@patch("backend.api.routes.credits.charge", return_value=1)
@patch("backend.api.routes.run_pipeline")
def test_create_job_accepts_motion_tier(mock_run_pipeline, mock_charge) -> None:
    client = _client()
    response = client.post("/jobs", json={"topic": "topic", "motion_tier": "basic"})

    assert response.status_code == 200
    assert response.json()["motion_tier"] == "basic"


@patch("backend.api.routes.credits.charge", return_value=4)
@patch("backend.api.routes.run_pipeline")
def test_get_job_roundtrip(mock_run_pipeline, mock_charge) -> None:
    client = _client()
    created = client.post("/jobs", json={"topic": "topic"}).json()

    fetched = client.get(f"/jobs/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_get_missing_job_returns_404() -> None:
    client = _client()
    response = client.get("/jobs/does-not-exist")
    assert response.status_code == 404


@patch("backend.api.routes.credits.charge", return_value=4)
def test_get_result_before_completion_returns_409(mock_charge) -> None:
    with patch("backend.api.routes.run_pipeline"):
        client = _client()
        created = client.post("/jobs", json={"topic": "topic"}).json()

    response = client.get(f"/jobs/{created['id']}/result")
    assert response.status_code == 409


@patch("backend.api.routes.credits.get_balance", return_value=42)
def test_get_credits_balance(mock_get_balance) -> None:
    client = _client()
    response = client.get("/credits")

    assert response.status_code == 200
    body = response.json()
    assert body["balance"] == 42
    assert set(body["cost_by_tier"].keys()) == {"max", "balanced", "basic"}


@patch("backend.api.routes.payments.create_order")
def test_create_order_returns_checkout_details(mock_create_order) -> None:
    mock_create_order.return_value = {
        "order_id": "order_123",
        "amount": 9900,
        "currency": "INR",
        "key_id": "rzp_test_fake",
        "credits": 50,
    }
    client = _client()
    response = client.post("/credits/create-order")

    assert response.status_code == 200
    assert response.json()["order_id"] == "order_123"


@patch("backend.api.routes.payments.create_order")
def test_create_order_returns_503_when_razorpay_not_configured(mock_create_order) -> None:
    from backend.services.payments import PaymentError

    mock_create_order.side_effect = PaymentError("RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured")
    client = _client()
    response = client.post("/credits/create-order")

    assert response.status_code == 503


@patch("backend.api.routes.credits.add_credits", return_value=50)
@patch("backend.api.routes.payments.verify_payment_signature")
def test_verify_payment_credits_account_on_success(mock_verify, mock_add_credits) -> None:
    from backend.core import orders

    # A signature alone is never enough - the order must have been opened by create-order.
    orders.create_pending("order_123", account="default", kind="legacy", credits=50, amount_paise=9900)
    client = _client()
    response = client.post(
        "/credits/verify-payment",
        json={
            "razorpay_order_id": "order_123",
            "razorpay_payment_id": "pay_456",
            "razorpay_signature": "deadbeef",
        },
    )

    assert response.status_code == 200
    assert response.json()["balance"] == 50
    assert response.json()["credits_added"] == 50
    mock_verify.assert_called_once_with(order_id="order_123", payment_id="pay_456", signature="deadbeef")
    mock_add_credits.assert_called_once_with(50, reason="razorpay:pay_456", account="default")


@patch("backend.api.routes.payments.verify_payment_signature")
def test_verify_payment_rejects_bad_signature(mock_verify) -> None:
    from backend.services.payments import SignatureVerificationError

    mock_verify.side_effect = SignatureVerificationError("payment signature did not match")
    client = _client()
    response = client.post(
        "/credits/verify-payment",
        json={
            "razorpay_order_id": "order_123",
            "razorpay_payment_id": "pay_456",
            "razorpay_signature": "wrong",
        },
    )

    assert response.status_code == 400


# --- Idempotency ---


@patch("backend.api.routes.credits.charge")
@patch("backend.api.routes.run_pipeline")
def test_create_job_with_same_idempotency_key_returns_same_job(mock_run_pipeline, mock_charge) -> None:
    mock_charge.return_value = 1
    client = _client()
    headers = {"Idempotency-Key": "test-key-123"}

    first = client.post("/jobs", json={"topic": "idempotent topic"}, headers=headers)
    second = client.post("/jobs", json={"topic": "idempotent topic"}, headers=headers)

    assert first.json()["id"] == second.json()["id"]
    mock_charge.assert_called_once()


# --- Lifecycle: approve / cancel / publish / quality-report ---


def _create_done_job(client) -> str:
    with patch("backend.api.routes.credits.charge", return_value=1), \
         patch("backend.api.routes.run_pipeline"):
        job_id = client.post("/jobs", json={"topic": "lifecycle topic"}).json()["id"]

    from backend.api.routes import job_manager
    from backend.models.schemas import JobStatus

    job_manager.update(job_id, status=JobStatus.DONE, result_path=f"storage/jobs/{job_id}/final.mp4")
    return job_id


def test_approve_rejects_job_not_done() -> None:
    client = _client()
    with patch("backend.api.routes.credits.charge", return_value=1), \
         patch("backend.api.routes.run_pipeline"):
        job_id = client.post("/jobs", json={"topic": "topic"}).json()["id"]

    response = client.post(f"/jobs/{job_id}/approve", json={"approver": "meet"})
    assert response.status_code == 409


def test_approve_then_publish_produces_manual_handoff(tmp_path) -> None:
    with patch("backend.config.settings.storage_dir", str(tmp_path)):
        client = _client()
        job_id = _create_done_job(client)

        approve_response = client.post(f"/jobs/{job_id}/approve", json={"approver": "meet"})
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "approved"

        publish_response = client.post(f"/jobs/{job_id}/publish")
        assert publish_response.status_code == 200
        body = publish_response.json()
        assert body["status"] == "manual_handoff"
        assert body["manual_handoff_path"]
        assert "NOT automatically published" in body["manual_handoff_note"]


def test_publish_rejects_job_not_approved() -> None:
    client = _client()
    job_id = _create_done_job(client)

    response = client.post(f"/jobs/{job_id}/publish")
    assert response.status_code == 409


def test_cancel_queued_job() -> None:
    client = _client()
    with patch("backend.api.routes.credits.charge", return_value=1), \
         patch("backend.api.routes.run_pipeline"):
        job_id = client.post("/jobs", json={"topic": "topic"}).json()["id"]

    response = client.post(f"/jobs/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_rejects_terminal_job() -> None:
    client = _client()
    job_id = _create_done_job(client)

    response = client.post(f"/jobs/{job_id}/cancel")
    assert response.status_code == 409


def test_quality_report_not_available_before_done() -> None:
    client = _client()
    with patch("backend.api.routes.credits.charge", return_value=1), \
         patch("backend.api.routes.run_pipeline"):
        job_id = client.post("/jobs", json={"topic": "topic"}).json()["id"]

    response = client.get(f"/jobs/{job_id}/quality-report")
    assert response.status_code == 409


# --- Meta endpoints ---


def test_providers_status_returns_chains_without_secrets() -> None:
    client = _client()
    response = client.get("/providers/status")
    assert response.status_code == 200
    body = response.json()
    assert "script" in body and "chain" in body["script"]
    assert "voice" in body and body["voice"]["chain"] == ["edge-tts", "gtts"]
    assert "auth" in body
    # Never leak raw secret values, only booleans
    assert all(isinstance(v, bool) for v in body["script"]["configured"].values())


def test_analytics_overview_counts_jobs_by_status() -> None:
    client = _client()
    with patch("backend.api.routes.credits.charge", return_value=1), \
         patch("backend.api.routes.run_pipeline"):
        client.post("/jobs", json={"topic": "a"})
        client.post("/jobs", json={"topic": "b"})

    response = client.get("/analytics/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["total_jobs"] >= 2
    assert "queued" in body["by_status"]


def test_ready_endpoint_reports_ffmpeg_check() -> None:
    client = _client()
    response = client.get("/ready")
    assert response.status_code in (200, 503)
    assert "ffmpeg" in response.json()["checks"]


# --- Auth gate ---


def test_create_job_requires_auth_when_api_key_configured() -> None:
    with patch("backend.api.routes.settings") as mock_settings:
        mock_settings.has_auth = True
        mock_settings.backend_api_key = "secret123"
        client = _client()
        response = client.post("/jobs", json={"topic": "topic"})
    assert response.status_code == 401


@patch("backend.api.routes.credits.charge", return_value=1)
@patch("backend.api.routes.run_pipeline")
def test_create_job_succeeds_with_correct_auth_header(mock_run_pipeline, mock_charge) -> None:
    with patch("backend.api.routes.settings") as mock_settings:
        mock_settings.has_auth = True
        mock_settings.backend_api_key = "secret123"
        client = _client()
        response = client.post(
            "/jobs", json={"topic": "topic"}, headers={"Authorization": "Bearer secret123"}
        )
    assert response.status_code == 200


# --- Login ---


def test_login_succeeds_when_auth_disabled() -> None:
    with patch("backend.api.routes.settings") as mock_settings:
        mock_settings.has_auth = False
        client = _client()
        response = client.post("/auth/login", json={"api_key": ""})
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "auth_required": False}


def test_login_succeeds_with_correct_key() -> None:
    with patch("backend.api.routes.settings") as mock_settings:
        mock_settings.has_auth = True
        mock_settings.backend_api_key = "secret123"
        client = _client()
        response = client.post("/auth/login", json={"api_key": "secret123"})
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "auth_required": True}


def test_login_rejects_wrong_key() -> None:
    with patch("backend.api.routes.settings") as mock_settings:
        mock_settings.has_auth = True
        mock_settings.backend_api_key = "secret123"
        client = _client()
        response = client.post("/auth/login", json={"api_key": "wrong"})
    assert response.status_code == 401
