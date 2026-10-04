from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.config import settings
from backend.core.exceptions import AllProvidersFailedError
from backend.models.schemas import JobStatus
from backend.services import prompt_booster
from backend.services.model_router import Provider, attempt_sink, call_with_fallback, redact


@pytest.fixture
def client() -> TestClient:
    from backend.api.routes import job_manager

    job_manager._jobs.clear()
    return TestClient(create_app())


@pytest.fixture
def no_ai_keys(monkeypatch):
    for name in ("gemini_api_key", "groq_api_key", "openrouter_api_key"):
        monkeypatch.setattr(settings, name, "")


def _token(client) -> dict:
    token = client.post("/auth/register", json={"email": "a@example.com", "password": "secret1"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


# --- prompt boost ---


def test_boost_falls_back_to_the_local_enhancer_when_no_ai_provider_is_configured(client, no_ai_keys) -> None:
    response = client.post("/prompt/boost", json={"prompt": "  why chai is safe.  "}, headers=_token(client))
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "local"
    assert "why chai is safe." in body["text"]
    assert body["text"] != "why chai is safe."


def test_boost_reports_which_provider_actually_answered(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "groq_api_key", "g")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    reply = MagicMock()
    reply.json.return_value = {"choices": [{"message": {"content": '```\n"A vivid rewritten prompt."\n```'}}]}
    reply.raise_for_status.return_value = None
    with patch("backend.services.prompt_booster.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = reply
        text, source = prompt_booster.boost("rough idea")
    assert source == "groq"
    assert text == "A vivid rewritten prompt."


def test_boost_survives_a_failing_provider_and_never_claims_ai_for_the_local_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with patch("backend.services.prompt_booster.httpx.Client", side_effect=RuntimeError("network down")):
        text, source = prompt_booster.boost("rough idea")
    assert source == "local"
    assert "rough idea" in text


def test_boost_validates_input(client, no_ai_keys) -> None:
    headers = _token(client)
    assert client.post("/prompt/boost", json={"prompt": "   "}, headers=headers).status_code == 422
    assert client.post("/prompt/boost", json={"prompt": "x" * 5000}, headers=headers).status_code == 422
    assert client.post("/prompt/boost", json={"prompt": "ok", "language": "klingon"}, headers=headers).status_code == 422


def test_boost_is_rate_limited(client, no_ai_keys) -> None:
    headers = _token(client)
    codes = [client.post("/prompt/boost", json={"prompt": "idea"}, headers=headers).status_code for _ in range(32)]
    assert codes[:30] == [200] * 30
    assert 429 in codes[30:]


def test_boost_requires_login_when_enforced(client, no_ai_keys, monkeypatch) -> None:
    monkeypatch.setattr(settings, "require_login", True)
    assert client.post("/prompt/boost", json={"prompt": "idea"}).status_code == 401


# --- provider attempt recording ---


def test_fallback_reports_each_attempt_in_order() -> None:
    events: list[dict] = []
    token = attempt_sink.set(events.append)
    try:
        def failing():
            raise RuntimeError("quota exceeded")

        result = call_with_fallback(
            [Provider("first", failing), Provider("second[2/3]", lambda: "done")], stage="generation.image"
        )
    finally:
        attempt_sink.reset(token)

    assert result == "done"
    assert events == [
        {"stage": "generation.image", "provider": "first", "ok": False, "error": "quota exceeded"},
        {"stage": "generation.image", "provider": "second", "ok": True, "error": None},
    ]


def test_no_events_are_recorded_without_a_sink() -> None:
    assert attempt_sink.get() is None
    assert call_with_fallback([Provider("only", lambda: 1)], stage="s") == 1


def test_a_broken_sink_never_breaks_generation() -> None:
    def explode(event):
        raise RuntimeError("sink bug")

    token = attempt_sink.set(explode)
    try:
        assert call_with_fallback([Provider("only", lambda: 7)], stage="s") == 7
    finally:
        attempt_sink.reset(token)


def test_provider_errors_are_scrubbed_of_credentials() -> None:
    leaky = "Client error '503' for url 'https://x.googleapis.com/v1/m:generate?key=AIzaSECRET123&alt=json'"
    events: list[dict] = []
    token = attempt_sink.set(events.append)
    try:
        def failing():
            raise RuntimeError(leaky)

        with pytest.raises(AllProvidersFailedError) as exc_info:
            call_with_fallback([Provider("gemini", failing)], stage="s")
    finally:
        attempt_sink.reset(token)

    assert "AIzaSECRET123" not in exc_info.value.reason
    assert "AIzaSECRET123" not in events[0]["error"]
    assert "key=***" in events[0]["error"]
    assert redact("Authorization: Bearer abc.def-123") == "Authorization: Bearer ***"


def test_pipeline_records_provider_events_on_the_job_and_cleans_up(monkeypatch) -> None:
    from backend.core import pipeline
    from backend.core.exceptions import PipelineError
    from backend.core.job_manager import JobManager

    manager = JobManager()
    job = manager.create("t")

    def fake_script(topic, language=None, **_style):
        call_with_fallback(
            [Provider("gemini", lambda: (_ for _ in ()).throw(RuntimeError("503"))), Provider("local_template", lambda: "ok")],
            stage="intelligence.story_engine",
        )
        raise PipelineError("intelligence.story_engine", "stop here")

    with patch.object(pipeline.story_engine, "generate_script", side_effect=fake_script):
        pipeline.run(job.id, manager)

    stored = manager.get(job.id)
    assert stored.status == JobStatus.FAILED
    assert [(e.provider, e.ok) for e in stored.provider_events] == [("gemini", False), ("local_template", True)]
    assert attempt_sink.get() is None  # the per-job sink must not leak into the next job on this thread
