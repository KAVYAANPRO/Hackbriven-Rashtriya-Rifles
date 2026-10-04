from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from backend.models.schemas import CaptionWord, Scene, SceneAssets, Script


@pytest.fixture(autouse=True)
def _no_real_mongo_by_default(monkeypatch):
    """Project-wide safety net: .env now carries a real MONGODB_URI for the
    live app, which backend/core/job_manager.py and backend/core/credits.py
    both read as a module-level `from backend.config import settings`
    singleton. Without this, any test that doesn't explicitly mock settings
    (e.g. tests/test_api.py, which drives the real job_manager singleton
    through TestClient) would silently hit the live database on every job
    create/update - confirmed live: it turned an ~80s offline suite into an
    8+ minute one hitting a real remote cluster repeatedly, and would have
    been writing test job documents into the real app's data.

    monkeypatch (not @patch) is used so this mutates the real settings
    singleton's attribute directly and auto-reverts after each test; any
    test that still wants real-Mongo behavior (e.g. the dedicated
    _mongo_mode fixtures in test_job_manager.py/test_credits.py) replaces
    `settings` wholesale with its own mock, which fully shadows this for
    that test's duration.
    """
    import backend.core.credits as credits_module
    import backend.core.job_manager as job_manager_module

    monkeypatch.setattr(job_manager_module.settings, "mongodb_uri", "")
    monkeypatch.setattr(credits_module.settings, "mongodb_uri", "")


@pytest.fixture(autouse=True)
def _isolated_storage_and_accounts(monkeypatch, tmp_path):
    """Every test gets its own storage dir (accounts.db, credits.db, uploads,
    session secret, job media) so nothing is written into the repo or shared
    between tests, and the in-memory rate limiter starts empty. `settings` is
    one shared singleton, so also forcing mongodb_uri off here covers the
    accounts/orders store - tests must never touch the real database."""
    import backend.core.security as security_module
    from backend.config import settings

    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "mongodb_uri", "")
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    monkeypatch.setattr(settings, "require_login", False)
    # Never send real email from tests, whatever .env says (tests that need mail turn it on and mock it).
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "email_verification", "auto")
    monkeypatch.setattr(settings, "admin_emails", "")
    monkeypatch.setattr(settings, "cloudflare_accounts", "")
    security_module.reset_secret_cache()
    security_module.reset_rate_limits()
    from backend.services import model_router

    model_router.reset_cooldowns()
    from backend.services import image_generator

    image_generator.reset_cloudflare_quota()
    yield
    security_module.reset_secret_cache()


@pytest.fixture
def sample_script() -> Script:
    return Script(
        topic="Why electric vehicles are becoming popular",
        hook="EVs are taking over the roads. Here's why.",
        mood="upbeat",
        scenes=[
            Scene(index=0, narration="EVs cut fuel costs.", image_prompt="ev charging at home", duration_seconds=4.0),
            Scene(index=1, narration="Governments offer big incentives.", image_prompt="government building with ev sign", duration_seconds=5.0),
            Scene(index=2, narration="Battery range keeps improving.", image_prompt="ev on a highway at sunset", duration_seconds=3.5),
        ],
    )


@pytest.fixture
def sample_scene_assets(tmp_path: Path) -> list[SceneAssets]:
    assets = []
    for i in range(2):
        image_path = tmp_path / f"scene_{i}.png"
        audio_path = tmp_path / f"scene_{i}.mp3"
        image_path.write_bytes(b"fake-image-bytes")
        audio_path.write_bytes(b"fake-audio-bytes")
        assets.append(
            SceneAssets(
                index=i,
                image_path=str(image_path),
                audio_path=str(audio_path),
                caption_words=[
                    CaptionWord(word="hello", start_seconds=0.0 + i, end_seconds=0.4 + i),
                    CaptionWord(word="world", start_seconds=0.4 + i, end_seconds=0.8 + i),
                ],
                duration_seconds=4.0,
            )
        )
    return assets
