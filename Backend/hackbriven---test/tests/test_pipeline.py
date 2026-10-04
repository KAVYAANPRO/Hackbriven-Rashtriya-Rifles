from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from backend.core import pipeline
from backend.core.job_manager import JobManager
from backend.models.schemas import CaptionWord, JobStatus, Language, QualityReport, Script
from backend.services import scene_planner


def test_pipeline_runs_to_done(tmp_path: Path, sample_script: Script):
    manager = JobManager()
    job = manager.create(sample_script.topic)

    with patch("backend.core.pipeline.settings") as mock_settings, \
         patch("backend.core.pipeline.story_engine.generate_script", return_value=sample_script), \
         patch("backend.core.pipeline.image_generator.generate_image") as mock_image, \
         patch("backend.core.pipeline.voice_generator.synthesize") as mock_voice, \
         patch("backend.core.pipeline.caption_generator.transcribe", return_value=[CaptionWord(word="hi", start_seconds=0, end_seconds=0.3)]), \
         patch("backend.core.pipeline.get_duration_seconds", return_value=4.0), \
         patch("backend.core.pipeline.music_generator.generate_ambient_bed") as mock_music, \
         patch("backend.core.pipeline.video_composer.compose") as mock_compose, \
         patch("backend.core.pipeline.quality_gate.check") as mock_check:

        mock_settings.storage_path = tmp_path
        mock_settings.max_regenerate_attempts = 2
        final_video = tmp_path / job.id / "final.mp4"
        music_path = tmp_path / job.id / "music.wav"
        mock_music.return_value = music_path
        mock_compose.return_value = final_video
        mock_check.return_value = QualityReport(passed=True, width=1080, height=1920, duration_seconds=12.5, has_audio_track=True)

        pipeline.run(job.id, manager)

    updated = manager.get(job.id)
    assert updated.status == JobStatus.DONE
    assert updated.result_path == str(final_video)
    assert updated.quality_report is not None and updated.quality_report.passed
    assert mock_image.call_count == 3  # one per scene in sample_script
    mock_music.assert_called_once()
    assert mock_compose.call_args.kwargs["music_path"] == music_path


def test_pipeline_continues_without_music_when_generation_fails(tmp_path: Path, sample_script: Script):
    manager = JobManager()
    job = manager.create(sample_script.topic)

    with patch("backend.core.pipeline.settings") as mock_settings, \
         patch("backend.core.pipeline.story_engine.generate_script", return_value=sample_script), \
         patch("backend.core.pipeline.image_generator.generate_image"), \
         patch("backend.core.pipeline.voice_generator.synthesize"), \
         patch("backend.core.pipeline.caption_generator.transcribe", return_value=[]), \
         patch("backend.core.pipeline.get_duration_seconds", return_value=4.0), \
         patch("backend.core.pipeline.music_generator.generate_ambient_bed", side_effect=RuntimeError("ffmpeg lavfi unavailable")), \
         patch("backend.core.pipeline.video_composer.compose") as mock_compose, \
         patch("backend.core.pipeline.quality_gate.check") as mock_check:

        mock_settings.storage_path = tmp_path
        mock_settings.max_regenerate_attempts = 2
        mock_compose.return_value = tmp_path / job.id / "final.mp4"
        mock_check.return_value = QualityReport(passed=True, width=1080, height=1920, duration_seconds=12.5, has_audio_track=True)

        pipeline.run(job.id, manager)

    updated = manager.get(job.id)
    assert updated.status == JobStatus.DONE  # music failure must not fail the job
    assert mock_compose.call_args.kwargs["music_path"] is None


def test_pipeline_retries_on_quality_gate_failure_then_fails(tmp_path: Path, sample_script: Script):
    manager = JobManager()
    job = manager.create(sample_script.topic)

    with patch("backend.core.pipeline.settings") as mock_settings, \
         patch("backend.core.pipeline.story_engine.generate_script", return_value=sample_script), \
         patch("backend.core.pipeline.image_generator.generate_image"), \
         patch("backend.core.pipeline.voice_generator.synthesize"), \
         patch("backend.core.pipeline.caption_generator.transcribe", return_value=[]), \
         patch("backend.core.pipeline.get_duration_seconds", return_value=4.0), \
         patch("backend.core.pipeline.music_generator.generate_ambient_bed"), \
         patch("backend.core.pipeline.video_composer.compose") as mock_compose, \
         patch("backend.core.pipeline.quality_gate.check") as mock_check:

        mock_settings.storage_path = tmp_path
        mock_settings.max_regenerate_attempts = 2
        mock_compose.return_value = tmp_path / job.id / "final.mp4"
        mock_check.return_value = QualityReport(passed=False, reasons=["no audio track found"])

        pipeline.run(job.id, manager)

    updated = manager.get(job.id)
    assert updated.status == JobStatus.FAILED
    assert updated.error_stage == "validation.quality_gate"
    assert "no audio track found" in (updated.error_reason or "")
    assert mock_compose.call_count == 3  # initial + 2 regenerate attempts


def test_generate_scene_assets_uses_actual_audio_duration_not_script_guess(tmp_path: Path, sample_script: Script):
    with patch("backend.core.pipeline.settings") as mock_settings, \
         patch("backend.core.pipeline.image_generator.generate_image"), \
         patch("backend.core.pipeline.voice_generator.synthesize"), \
         patch("backend.core.pipeline.caption_generator.transcribe", return_value=[]), \
         patch("backend.core.pipeline.get_duration_seconds", return_value=9.75) as mock_get_duration:

        mock_settings.storage_path = tmp_path
        plan = scene_planner.plan(sample_script)

        assets = pipeline._generate_scene_assets("job123", plan, Language.EN)

    assert mock_get_duration.call_count == len(sample_script.scenes)
    assert all(asset.duration_seconds == 9.75 for asset in assets)
    # the script's own (guessed) durations differ from 9.75, proving the
    # real measured audio duration was used, not scene.duration_seconds
    assert not any(s.duration_seconds == 9.75 for s in sample_script.scenes)


def test_pipeline_marks_failed_on_story_engine_error(tmp_path: Path, sample_script: Script):
    from backend.core.exceptions import AllProvidersFailedError

    manager = JobManager()
    job = manager.create(sample_script.topic)

    with patch("backend.core.pipeline.settings") as mock_settings, \
         patch("backend.core.pipeline.story_engine.generate_script", side_effect=AllProvidersFailedError("intelligence.story_engine", [("gemini", "rate limited"), ("groq", "rate limited")])):
        mock_settings.storage_path = tmp_path

        pipeline.run(job.id, manager)

    updated = manager.get(job.id)
    assert updated.status == JobStatus.FAILED
    assert updated.error_stage == "intelligence.story_engine"
