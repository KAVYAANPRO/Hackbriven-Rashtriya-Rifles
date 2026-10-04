from __future__ import annotations

import pytest

from backend.config import settings
from backend.core.job_manager import JobManager
from backend.core.pipeline import run as run_pipeline
from backend.models.schemas import JobStatus
from backend.utils.ffmpeg_utils import FfmpegNotAvailableError, _resolve_binaries

pytestmark = pytest.mark.integration


def _ffmpeg_available() -> bool:
    """PATH first, static-ffmpeg fallback second - same resolution the real
    pipeline uses, so this skip check can't disagree with reality."""
    try:
        _resolve_binaries()
        return True
    except FfmpegNotAvailableError:
        return False


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg/ffprobe unavailable (PATH and static-ffmpeg fallback both failed)")
def test_full_pipeline_runs_end_to_end_with_keyless_providers(tmp_path, monkeypatch):
    """Real network calls, real ffmpeg, zero API keys.

    Forces every stage onto its keyless path (local-template script,
    Pollinations images, edge-tts voice, real Whisper if installed) and
    asserts the job reaches DONE with a playable MP4 on disk. Opt in with:
    `pytest -m integration`.
    """
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))

    manager = JobManager()
    job = manager.create("Why electric vehicles are becoming popular")

    run_pipeline(job.id, manager)

    updated = manager.get(job.id)
    assert updated.status == JobStatus.DONE, (updated.error_stage, updated.error_reason)
    assert updated.result_path
    from pathlib import Path

    assert Path(updated.result_path).exists()
    assert updated.quality_report is not None
    assert updated.quality_report.passed
