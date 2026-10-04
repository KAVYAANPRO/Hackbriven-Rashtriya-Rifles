from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.config import settings
from backend.core import credits, security, users
from backend.models.schemas import JobStatus, MotionTier
from backend.services import styles


@pytest.fixture
def client() -> TestClient:
    from backend.api.routes import job_manager

    job_manager._jobs.clear()
    return TestClient(create_app())


def _token(client, email="a@example.com") -> dict:
    token = client.post("/auth/register", json={"email": email, "password": "secret1"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _create(client, headers, **body):
    with patch("backend.api.routes.run_pipeline"):
        return client.post("/jobs", json={"topic": "a topic", "motion_tier": "basic", **body}, headers=headers)


# --- catalog ---


def test_plans_lists_styles_resolutions_and_formats(client) -> None:
    body = client.get("/plans").json()
    style_ids = [s["id"] for s in body["styles"]]
    assert style_ids[0] == "auto" and "custom" in style_ids
    assert {"cinematic", "minimalist", "playful", "3d", "colorful"} <= set(style_ids)
    assert [r["id"] for r in body["resolutions"]] == ["720p", "1080p", "4k"]
    assert next(r for r in body["resolutions"] if r["id"] == "4k")["credit_surcharge"] > 0
    assert [f["id"] for f in body["formats"]] == ["mp4", "mov", "webm", "mkv", "gif", "mp3"]
    free = next(p for p in body["plans"] if p["id"] == "free")
    assert "4k" not in free["resolutions"]
    assert all("tone" not in s and "visual" not in s for s in body["styles"])  # prompt internals stay server-side


def test_credits_reports_allowed_resolutions(client) -> None:
    headers = _token(client)
    assert client.get("/credits", headers=headers).json()["resolutions_allowed"] == ["720p"]


# --- creating jobs with style + resolution ---


def test_job_records_style_and_resolution(client) -> None:
    response = _create(client, _token(client), style="playful", resolution="720p")
    assert response.status_code == 200
    body = response.json()
    assert (body["style"], body["resolution"], body["style_prompt"]) == ("playful", "720p", None)


def test_custom_style_requires_text_and_is_sanitised(client) -> None:
    headers = _token(client)
    assert _create(client, headers, style="custom").status_code == 422
    assert _create(client, headers, style="custom", style_prompt="   ").status_code == 422
    ok = _create(client, headers, style="custom", style_prompt="  pastel   claymation\nlook " + "x" * 400)
    assert ok.status_code == 200
    stored = ok.json()["style_prompt"]
    assert stored.startswith("pastel claymation look") and len(stored) == styles.MAX_CUSTOM_CHARS


def test_unknown_style_or_resolution_is_rejected_without_charging(client) -> None:
    headers = _token(client)
    assert _create(client, headers, style="vaporwave-9000").status_code == 422
    assert _create(client, headers, resolution="8k").status_code == 422
    assert credits.get_balance("a@example.com") == settings.signup_credits


def test_free_plan_cannot_order_4k(client) -> None:
    response = _create(client, _token(client), resolution="4k")
    assert response.status_code == 403
    assert response.json()["detail"]["required_plan"] == "studio"
    assert credits.get_balance("a@example.com") == settings.signup_credits


def test_pro_plan_cannot_order_4k(client) -> None:
    headers = _token(client)
    users.activate_plan("a@example.com", "pro")
    response = _create(client, headers, resolution="4k")
    assert response.status_code == 403
    assert response.json()["detail"]["required_plan"] == "studio"


def test_4k_charges_the_resolution_surcharge(client) -> None:
    headers = _token(client)
    users.activate_plan("a@example.com", "studio")
    assert _create(client, headers, resolution="4k").status_code == 200
    expected = credits.cost_for_tier(MotionTier.BASIC) + 3
    assert credits.get_balance("a@example.com") == settings.signup_credits - expected


# --- downloads ---


def _done_job(client, headers) -> dict:
    from backend.api.routes import job_manager

    job = _create(client, headers).json()
    job_dir = settings.storage_path / job["id"]
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "final.mp4").write_bytes(b"master-bytes")
    job_manager.update(job["id"], status=JobStatus.DONE, result_path=str(job_dir / "final.mp4"))
    return job


def test_download_converts_and_names_the_file(client) -> None:
    headers = _token(client)
    job = _done_job(client, headers)
    sig = security.media_sig(job["id"])

    def fake_export(job_dir, fmt_id):
        out = job_dir / f"video.{fmt_id}"
        out.write_bytes(b"converted-" + fmt_id.encode())
        return out

    with patch("backend.api.routes.exporter.export_format", side_effect=fake_export) as mock_export:
        response = client.get(f"/jobs/{job['id']}/download", params={"format": "webm", "sig": sig})
    assert response.status_code == 200
    assert response.content == b"converted-webm"
    assert response.headers["content-type"] == "video/webm"
    assert f'ideafeed-{job["id"]}.webm' in response.headers["content-disposition"]
    assert mock_export.call_args.args[1] == "webm"


def test_download_validation(client) -> None:
    headers = _token(client)
    job = _done_job(client, headers)
    sig = security.media_sig(job["id"])
    assert client.get(f"/jobs/{job['id']}/download", params={"format": "avi9", "sig": sig}).status_code == 422
    assert client.get(f"/jobs/{job['id']}/download", params={"format": "mov"}).status_code == 404  # no sig, no login

    pending = _create(client, headers).json()
    assert client.get(
        f"/jobs/{pending['id']}/download", params={"format": "mov", "sig": security.media_sig(pending["id"])}
    ).status_code == 409


def test_mp4_download_is_the_master_itself(client) -> None:
    headers = _token(client)
    job = _done_job(client, headers)
    response = client.get(f"/jobs/{job['id']}/download", params={"format": "mp4", "sig": security.media_sig(job["id"])})
    assert response.status_code == 200
    assert response.content == b"master-bytes"


# --- styles feed the prompts ---


def test_style_changes_script_instructions_and_image_prompts() -> None:
    from backend.models.schemas import Language
    from backend.services import story_engine

    system = story_engine._build_system_prompt(Language.EN, "playful")
    assert "humour" in system
    assert "Never depict a real person's face" in system

    styled = styles.apply_to_image_prompt("two race cars on a track", "3d")
    assert styled.startswith("stylized 3D animated render")  # the style leads the prompt
    assert "two race cars on a track" in styled
    assert "no watermark" in styled
    assert styles.apply_to_image_prompt("x", "auto").endswith("no watermark")
    assert "claymation" in styles.apply_to_image_prompt("x", "custom", "claymation")


def test_boost_accepts_a_style_and_rejects_unknown_ones(client, monkeypatch) -> None:
    for name in ("gemini_api_key", "groq_api_key", "openrouter_api_key"):
        monkeypatch.setattr(settings, name, "")
    headers = _token(client)
    assert client.post("/prompt/boost", json={"prompt": "idea", "style": "neon"}, headers=headers).status_code == 200
    assert client.post("/prompt/boost", json={"prompt": "idea", "style": "nope"}, headers=headers).status_code == 422


def test_booster_instructions_protect_names_and_the_versus_angle() -> None:
    from backend.models.schemas import Language
    from backend.services import prompt_booster

    system = prompt_booster._system_prompt(Language.HINGLISH, "cinematic")
    assert "head-to-head comparison" in system
    assert "Never invent statistics" in system
    assert "ONLY Latin/English letters" in system
    assert "Cinematic" in system


def test_quality_gate_checks_the_delivered_resolution(tmp_path) -> None:
    from backend.services import quality_gate

    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    fake = {
        "streams": [{"codec_type": "video", "width": 720, "height": 1280}, {"codec_type": "audio", "channels": 2}],
        "format": {"duration": "30.0"},
    }
    with patch("backend.services.quality_gate.probe", return_value=fake):
        assert quality_gate.check(video, 30.0, expected_width=720, expected_height=1280).passed
        assert not quality_gate.check(video, 30.0).passed  # default expectation is 1080x1920
