from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.config import settings
from backend.core import security
from backend.models.schemas import JobStatus
from backend.services import mailer

OWNER = "kavya@example.com"


@pytest.fixture
def client(monkeypatch) -> TestClient:
    from backend.api.routes import job_manager

    job_manager._jobs.clear()
    # Pretend SMTP is configured; the transport itself is always mocked below - no network.
    monkeypatch.setattr(settings, "smtp_host", "smtp.invalid")
    monkeypatch.setattr(settings, "smtp_user", "sender@example.com")
    monkeypatch.setattr(settings, "public_api_url", "https://api.example.com/")
    return TestClient(create_app())


def _auth(email: str) -> dict:
    return {"Authorization": f"Bearer {security.issue_token(email)}"}


def _finished_job(owner: str | None = OWNER, *, status: JobStatus = JobStatus.DONE, video_bytes: bytes = b"mp4data"):
    from backend.api.routes import job_manager

    job = job_manager.create("Why EVs are popular", owner=owner)
    job_dir = settings.storage_path / job.id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "final.mp4").write_bytes(video_bytes)
    return job_manager.update(job.id, status=status, result_path=str(job_dir / "final.mp4"))


def test_email_endpoint_queues_and_masks_recipient(client) -> None:
    job = _finished_job()
    with patch("backend.services.mailer.send") as send:
        response = client.post(f"/jobs/{job.id}/email", headers=_auth(OWNER))
    assert response.status_code == 200, response.text
    assert response.json() == {"queued": True, "to": "k***@example.com"}
    send.assert_called_once()
    to, subject = send.call_args.args[0], send.call_args.args[1]
    assert to == OWNER
    assert subject == "Your video is ready: Why EVs are popular"
    attachments = send.call_args.kwargs["attachments"]
    assert attachments[0][0].endswith(".mp4") and attachments[0][2] == b"mp4data"


def test_email_endpoint_is_owner_only(client) -> None:
    job = _finished_job()
    with patch("backend.services.mailer.send") as send:
        response = client.post(f"/jobs/{job.id}/email", headers=_auth("someone@else.com"))
    assert response.status_code == 404
    send.assert_not_called()


def test_email_endpoint_409_without_finished_video(client) -> None:
    from backend.api.routes import job_manager

    job = job_manager.create("not done yet", owner=OWNER)
    with patch("backend.services.mailer.send") as send:
        response = client.post(f"/jobs/{job.id}/email", headers=_auth(OWNER))
    assert response.status_code == 409
    send.assert_not_called()


def test_email_endpoint_409_for_anonymous_job(client) -> None:
    job = _finished_job(owner=None)
    with patch("backend.services.mailer.send") as send:
        response = client.post(f"/jobs/{job.id}/email")  # anonymous caller owns the anonymous job
    assert response.status_code == 409
    send.assert_not_called()


def test_email_endpoint_503_when_smtp_not_configured(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "")
    job = _finished_job()
    response = client.post(f"/jobs/{job.id}/email", headers=_auth(OWNER))
    assert response.status_code == 503


def test_email_endpoint_rate_limited_per_job(client) -> None:
    job = _finished_job()
    with patch("backend.services.mailer.send") as send:
        first = client.post(f"/jobs/{job.id}/email", headers=_auth(OWNER))
        second = client.post(f"/jobs/{job.id}/email", headers=_auth(OWNER))
    assert first.status_code == 200
    assert second.status_code == 429
    assert send.call_count == 1


def test_large_video_gets_signed_link_instead_of_attachment(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_attachment_max_mb", 0.000001)
    job = _finished_job(video_bytes=b"x" * 1000)
    with patch("backend.services.mailer.send") as send:
        assert client.post(f"/jobs/{job.id}/email", headers=_auth(OWNER)).status_code == 200
    text = send.call_args.args[2]
    expected = f"https://api.example.com/jobs/{job.id}/video?download=true&sig={security.media_sig(job.id)}"
    assert expected in text
    # the large video is linked, not attached; the small handoff note is always attached
    assert [a[0] for a in send.call_args.kwargs["attachments"]] == [f"qoneqt_handoff_{job.id}.txt"]


def test_approve_auto_sends_video_email(client) -> None:
    job = _finished_job()
    with patch("backend.services.mailer.send") as send:
        response = client.post(f"/jobs/{job.id}/approve", json={"approver": "me"}, headers=_auth(OWNER))
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    send.assert_called_once()
    assert send.call_args.args[0] == OWNER


def test_approve_succeeds_even_if_email_fails(client) -> None:
    job = _finished_job()
    with patch("backend.services.mailer.send", side_effect=mailer.MailError("boom")):
        response = client.post(f"/jobs/{job.id}/approve", json={"approver": "me"}, headers=_auth(OWNER))
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_manual_handoff_email_includes_handoff_note(client) -> None:
    job = _finished_job(status=JobStatus.APPROVED)
    with patch("backend.services.mailer.send") as send:
        response = client.post(f"/jobs/{job.id}/publish", headers=_auth(OWNER))
    assert response.status_code == 200
    assert response.json()["status"] == "manual_handoff"
    send.assert_called_once()
    assert "Manual handoff note" in send.call_args.args[2]
    names = [a[0] for a in send.call_args.kwargs["attachments"]]
    assert any(n.startswith("qoneqt_handoff_") for n in names)


def test_send_video_email_returns_false_without_smtp(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "")
    job = _finished_job()
    with patch("backend.services.mailer.send") as send:
        assert mailer.send_video_email(job, settings.storage_path / job.id) is False
    send.assert_not_called()


def test_mask_email() -> None:
    assert mailer.mask_email("kavya@gmail.com") == "k***@gmail.com"
    assert mailer.mask_email("nope") == "***"
