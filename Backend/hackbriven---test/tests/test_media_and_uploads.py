from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.api.main import create_app
from backend.config import settings
from backend.core import credits, security
from backend.models.schemas import JobStatus, ScenePlan, ScenePlanSet


@pytest.fixture
def client() -> TestClient:
    from backend.api.routes import job_manager

    job_manager._jobs.clear()
    return TestClient(create_app())


def _register(client, email="a@example.com") -> str:
    return client.post("/auth/register", json={"email": email, "password": "secret1"}).json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _png(width=40, height=30, color=(200, 30, 30), fmt="PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format=fmt)
    return buffer.getvalue()


def _upload(client, token, files: list[tuple[str, bytes, str]]):
    return client.post(
        "/uploads",
        files=[("files", (name, data, mime)) for name, data, mime in files],
        headers=_auth(token),
    )


# --- uploads ---


def test_upload_stores_images_cropped_to_the_video_frame(client) -> None:
    token = _register(client)
    response = _upload(client, token, [("cat.png", _png(), "image/png"), ("dog.jpg", _png(fmt="JPEG"), "image/jpeg")])
    assert response.status_code == 200
    files = response.json()["files"]
    assert [f["name"] for f in files] == ["cat.png", "dog.jpg"]
    assert files[0]["width"] == 40 and files[0]["height"] == 30

    from backend.services import uploads

    stored = Image.open(uploads.path_for(files[0]["id"]))
    assert stored.size == (settings.target_width, settings.target_height)


def test_upload_rejects_non_images_and_oversize_and_too_many(client, monkeypatch) -> None:
    token = _register(client)
    assert _upload(client, token, [("notes.txt", b"hello world", "text/plain")]).status_code == 415
    assert _upload(client, token, [("fake.png", b"\x89PNG not really", "image/png")]).status_code == 415
    assert _upload(client, token, [("empty.png", b"", "image/png")]).status_code == 422

    monkeypatch.setattr(settings, "max_upload_bytes", 100)
    assert _upload(client, token, [("big.png", _png(200, 200), "image/png")]).status_code == 413

    monkeypatch.setattr(settings, "max_upload_bytes", 10 * 1024 * 1024)
    monkeypatch.setattr(settings, "max_upload_images", 2)
    three = [(f"{i}.png", _png(), "image/png") for i in range(3)]
    assert _upload(client, token, three).status_code == 422


def test_upload_requires_login_when_enforced(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "require_login", True)
    response = client.post("/uploads", files=[("files", ("a.png", _png(), "image/png"))])
    assert response.status_code == 401


def test_job_accepts_own_reference_images_and_rejects_foreign_or_bogus_ids(client) -> None:
    token_a = _register(client, "a@example.com")
    token_b = _register(client, "b@example.com")
    mine = _upload(client, token_a, [("a.png", _png(), "image/png")]).json()["files"][0]["id"]

    with patch("backend.api.routes.run_pipeline"):
        ok = client.post(
            "/jobs", json={"topic": "t", "motion_tier": "basic", "reference_images": [mine]}, headers=_auth(token_a)
        )
        foreign = client.post(
            "/jobs", json={"topic": "t", "motion_tier": "basic", "reference_images": [mine]}, headers=_auth(token_b)
        )
        bogus = client.post(
            "/jobs", json={"topic": "t", "motion_tier": "basic", "reference_images": ["../../etc/passwd"]}, headers=_auth(token_a)
        )
    assert ok.status_code == 200
    assert ok.json()["reference_images"] == [mine]
    assert foreign.status_code == 422
    assert bogus.status_code == 422
    # a rejected request must not have charged anything
    assert credits.get_balance("b@example.com") == settings.signup_credits


def test_pipeline_uses_reference_images_as_the_first_scene_visuals(tmp_path, monkeypatch) -> None:
    from backend.core import pipeline
    from backend.services import uploads

    monkeypatch.setattr(settings, "target_width", 64)
    monkeypatch.setattr(settings, "target_height", 96)
    info = uploads.save_image("default", "ref.png", _png(50, 50, color=(10, 200, 10)))
    ref_path = uploads.path_for(info["id"])

    plan = ScenePlanSet(
        topic="t",
        hook="h",
        scenes=[
            ScenePlan(index=i, narration=f"n{i}", image_prompt=f"p{i}", duration_seconds=2, start_offset_seconds=2 * i, end_offset_seconds=2 * i + 2)
            for i in range(2)
        ],
    )
    generated: list[str] = []

    def fake_generate(prompt, out_path):
        generated.append(prompt)
        Image.new("RGB", (64, 96)).save(out_path)

    with patch.object(pipeline.image_generator, "generate_image", side_effect=fake_generate), \
         patch.object(pipeline.voice_generator, "synthesize"), \
         patch.object(pipeline.caption_generator, "transcribe", return_value=[]), \
         patch.object(pipeline, "get_duration_seconds", return_value=2.0):
        from backend.models.schemas import Language

        assets = pipeline._generate_scene_assets("jobref", plan, Language.EN, [ref_path])

    # scene 0 came from the upload; only scene 1 was AI-generated (its prompt now carries framing rules)
    assert len(generated) == 1 and generated[0].startswith("p1")
    # the square upload is shown whole in the middle of the frame (corners are its blurred backdrop)
    assert Image.open(assets[0].image_path).getpixel((32, 48)) == (10, 200, 10)


# --- media ---


def _finished_job(client, token, *, with_video=True) -> dict:
    with patch("backend.api.routes.run_pipeline"):
        job = client.post("/jobs", json={"topic": "t", "motion_tier": "basic"}, headers=_auth(token)).json()
    from backend.api.routes import job_manager

    job_dir = settings.storage_path / job["id"]
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "scene_00.png").write_bytes(_png())
    scene_plan = ScenePlanSet(
        topic="t",
        hook="hook line",
        scenes=[ScenePlan(index=i, narration="n", image_prompt="p", duration_seconds=2, start_offset_seconds=0, end_offset_seconds=2) for i in range(3)],
    )
    fields = {"status": JobStatus.DONE, "scene_plan": scene_plan}
    if with_video:
        (job_dir / "final.mp4").write_bytes(b"0123456789" * 100)
        fields["result_path"] = str(job_dir / "final.mp4")
    job_manager.update(job["id"], **fields)
    return job


def test_job_view_exposes_media_state(client) -> None:
    token = _register(client)
    job = _finished_job(client, token)
    view = client.get(f"/jobs/{job['id']}", headers=_auth(token)).json()
    assert view["media_sig"] == security.media_sig(job["id"])
    assert view["has_video"] is True
    assert view["ready_scene_images"] == [0]  # only scene 0's image exists on disk


def test_video_is_served_with_a_valid_signature_and_supports_range(client) -> None:
    token = _register(client)
    job = _finished_job(client, token)
    sig = security.media_sig(job["id"])

    full = client.get(f"/jobs/{job['id']}/video", params={"sig": sig})
    assert full.status_code == 200
    assert full.headers["content-type"] == "video/mp4"
    assert len(full.content) == 1000

    partial = client.get(f"/jobs/{job['id']}/video", params={"sig": sig}, headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206
    assert len(partial.content) == 100

    download = client.get(f"/jobs/{job['id']}/video", params={"sig": sig, "download": "true"})
    assert "attachment" in download.headers["content-disposition"]


def test_media_needs_a_signature_or_the_owners_login(client) -> None:
    token_a = _register(client, "a@example.com")
    token_b = _register(client, "b@example.com")
    job = _finished_job(client, token_a)
    url = f"/jobs/{job['id']}/video"

    assert client.get(url).status_code == 404  # anonymous, no signature
    assert client.get(url, params={"sig": "0" * 32}).status_code == 404
    assert client.get(url, headers=_auth(token_b)).status_code == 404  # someone else's job
    assert client.get(url, headers=_auth(token_a)).status_code == 200  # the owner's own login works too
    assert client.get(f"/jobs/{job['id']}/scenes/0/image", params={"sig": security.media_sig(job['id'])}).status_code == 200


def test_signature_for_one_job_does_not_open_another(client) -> None:
    token = _register(client)
    first = _finished_job(client, token)
    second = _finished_job(client, token)
    assert client.get(f"/jobs/{second['id']}/video", params={"sig": security.media_sig(first["id"])}).status_code == 404


def test_video_and_scene_image_before_they_exist(client) -> None:
    token = _register(client)
    job = _finished_job(client, token, with_video=False)
    sig = security.media_sig(job["id"])
    assert client.get(f"/jobs/{job['id']}/video", params={"sig": sig}).status_code == 409
    assert client.get(f"/jobs/{job['id']}/scenes/2/image", params={"sig": sig}).status_code == 404
    assert client.get(f"/jobs/{job['id']}/scenes/-1/image", params={"sig": sig}).status_code == 404


def test_approve_publish_then_download_the_handoff(client) -> None:
    token = _register(client)
    job = _finished_job(client, token)
    sig = security.media_sig(job["id"])
    assert client.get(f"/jobs/{job['id']}/handoff", params={"sig": sig}).status_code == 409  # nothing published yet

    assert client.post(f"/jobs/{job['id']}/approve", json={"approver": "me@x.com"}, headers=_auth(token)).status_code == 200
    published = client.post(f"/jobs/{job['id']}/publish", headers=_auth(token))
    assert published.status_code == 200
    assert published.json()["status"] == "manual_handoff"

    handoff = client.get(f"/jobs/{job['id']}/handoff", params={"sig": sig})
    assert handoff.status_code == 200
    assert "NOT automatically published" in handoff.text
    assert "attachment" in handoff.headers["content-disposition"]


def test_publish_is_idempotent_and_retryable_after_failure(client) -> None:
    from backend.api.routes import job_manager

    token = _register(client)
    job = _finished_job(client, token)
    client.post(f"/jobs/{job['id']}/approve", json={"approver": "me"}, headers=_auth(token))

    with patch("backend.api.routes.qoneqt_handoff.build_handoff", side_effect=OSError("disk full")):
        failed = client.post(f"/jobs/{job['id']}/publish", headers=_auth(token)).json()
    assert failed["status"] == "publish_failed"
    assert "disk full" in failed["publish_error"]

    retry = client.post(f"/jobs/{job['id']}/publish", headers=_auth(token)).json()
    assert retry["status"] == "manual_handoff"
    assert retry["publish_error"] is None

    again = client.post(f"/jobs/{job['id']}/publish", headers=_auth(token))
    assert again.status_code == 200
    assert again.json()["status"] == "manual_handoff"
    assert job_manager.get(job["id"]).status == JobStatus.MANUAL_HANDOFF


def test_cancelled_job_is_not_resurrected_by_an_in_flight_stage() -> None:
    from backend.core.job_manager import JobManager

    manager = JobManager()
    job = manager.create("t")
    manager.cancel(job.id)
    manager.set_status(job.id, JobStatus.DONE)
    assert manager.get(job.id).status == JobStatus.CANCELLED
