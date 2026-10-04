from __future__ import annotations

import logging
import shutil
from pathlib import Path

from backend.config import settings
from backend.core import plans
from backend.core.exceptions import PipelineError
from backend.core.job_manager import JobManager
from backend.models.schemas import JobStatus, Language, ProviderEvent, SceneAssets, ScenePlanSet
from backend.services import (
    caption_generator,
    captions,
    image_generator,
    music_generator,
    exporter,
    quality_gate,
    scene_planner,
    story_engine,
    styles,
    uploads,
    video_composer,
    voice_generator,
)
from backend.services.model_router import attempt_sink, redact
from backend.utils.ffmpeg_utils import get_duration_seconds

logger = logging.getLogger(__name__)


def _job_dir(job_id: str) -> Path:
    path = settings.storage_path / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _generate_scene_assets(
    job_id: str,
    plan: ScenePlanSet,
    language: Language,
    reference_paths: list[Path] | None = None,
    style: str = "auto",
    style_prompt: str | None = None,
) -> list[SceneAssets]:
    job_dir = _job_dir(job_id)
    assets: list[SceneAssets] = []
    references = reference_paths or []

    for scene in plan.scenes:
        image_path = job_dir / f"scene_{scene.index:02d}.png"
        audio_path = job_dir / f"scene_{scene.index:02d}.mp3"

        # The creator's own images are the visuals of the first scenes, in the
        # order they were uploaded (already cropped to the video frame at
        # upload time); only the remaining scenes are AI-generated.
        if scene.index < len(references):
            shutil.copyfile(references[scene.index], image_path)
        else:
            image_generator.generate_image(
                styles.apply_to_image_prompt(scene.image_prompt, style, style_prompt), image_path
            )
        voice_generator.synthesize(scene.narration, audio_path, language=language)

        # The script's duration_seconds is only ever a guess (an LLM or the
        # local template estimating how long narration "should" take to
        # read); edge-tts's actual spoken-audio length is what the Ken Burns
        # clip and the final video must match, or video/audio drift out of
        # sync and the quality gate correctly rejects the result. Always
        # measure the real synthesized audio instead of trusting the guess.
        actual_duration = get_duration_seconds(audio_path)
        caption_words = caption_generator.caption_words_for(
            audio_path, scene.narration, language=language, duration_seconds=actual_duration
        )

        assets.append(
            SceneAssets(
                index=scene.index,
                image_path=str(image_path),
                audio_path=str(audio_path),
                caption_words=caption_words,
                duration_seconds=actual_duration,
                image_prompt=styles.apply_to_image_prompt(scene.image_prompt, style, style_prompt),
            )
        )

    return assets


def _expected_size(job) -> dict:
    resolution = plans.resolution_def(job.resolution) or plans.resolution_def(plans.DEFAULT_RESOLUTION)
    return {"expected_width": resolution.width, "expected_height": resolution.height}


def _compose_and_deliver(assets: list[SceneAssets], job, music_path: Path | None) -> Path:
    """Compose the 1080p master, then deliver it at the resolution the user chose."""
    job_dir = _job_dir(job.id)
    composed = video_composer.compose(
        assets,
        job_dir,
        music_path=music_path,
        motion_tier=job.motion_tier,
        captions=job.captions,
        caption_scenes=captions.display_scenes(captions.load_source(job_dir), job.captions, job.language),
    )
    return exporter.deliver_at_resolution(job_dir, composed, job.resolution)


def run(job_id: str, job_manager: JobManager, *, topic: str | None = None) -> None:
    """Run the full pipeline for a job: Intelligence -> Generation ->
    Composition -> Validation -> Output.

    Catches PipelineError at the boundary and marks the job FAILED with the
    stage + reason attached, per RULES.md #7. Any stage may raise it; nothing
    proceeds past a failed stage.
    """
    job = job_manager.get(job_id)
    resolved_topic = topic or job.topic

    def _cancelled() -> bool:
        return job_manager.get(job_id).status == JobStatus.CANCELLED

    def _record_attempt(event: dict) -> None:
        job_manager.add_provider_event(job_id, ProviderEvent(**event))

    # Report every provider attempt for this job (this thread only) so the
    # frontend can show real fallbacks. Reset in `finally` - background
    # tasks reuse threads.
    sink_token = attempt_sink.set(_record_attempt)

    try:
        if _cancelled():
            return
        job_manager.set_status(job_id, JobStatus.RUNNING_INTELLIGENCE)
        script = story_engine.generate_script(
            resolved_topic, language=job.language, style=job.style, style_prompt=job.style_prompt
        )
        plan = scene_planner.plan(script)
        job_manager.update(job_id, script=script, scene_plan=plan)

        if _cancelled():
            return
        job_manager.set_status(job_id, JobStatus.RUNNING_GENERATION)
        reference_paths = [
            path for path in (uploads.path_for(i) for i in job.reference_images) if path.exists()
        ]
        assets = _generate_scene_assets(job_id, plan, job.language, reference_paths, job.style, job.style_prompt)
        expected_duration = sum(asset.duration_seconds for asset in assets)
        captions.save_source(_job_dir(job_id), assets, {sc.index: sc.narration for sc in plan.scenes})

        if _cancelled():
            return
        job_manager.set_status(job_id, JobStatus.RUNNING_COMPOSITION)
        music_path = None
        try:
            music_path = music_generator.generate_ambient_bed(
                styles.music_mood(job.style) or script.mood, expected_duration, _job_dir(job_id) / "music.wav"
            )
        except Exception as exc:  # noqa: BLE001 - background music is optional, never fail the job for it
            logger.warning("job=%s background music generation failed, continuing without it: %s", job_id, exc)
        video_path = _compose_and_deliver(assets, job, music_path)

        if _cancelled():
            return
        job_manager.set_status(job_id, JobStatus.RUNNING_VALIDATION)
        report = quality_gate.check(video_path, expected_duration, **_expected_size(job))

        attempts = 0
        while not report.passed and attempts < settings.max_regenerate_attempts:
            attempts += 1
            logger.warning(
                "job=%s quality gate failed (attempt %s): %s",
                job_id, attempts, report.reasons,
            )
            video_path = _compose_and_deliver(assets, job, music_path)
            report = quality_gate.check(video_path, expected_duration, **_expected_size(job))

        job_manager.update(job_id, quality_report=report)

        if not report.passed:
            job_manager.mark_failed(
                job_id,
                stage="validation.quality_gate",
                reason="; ".join(report.reasons) or "quality gate failed",
            )
            return

        if _cancelled():
            return
        job_manager.update(job_id, result_path=str(video_path))
        job_manager.set_status(job_id, JobStatus.DONE)

    except PipelineError as exc:
        job_manager.mark_failed(job_id, stage=exc.stage, reason=exc.reason)
    except Exception as exc:  # noqa: BLE001 - last-resort boundary, never leak raw errors
        logger.exception("job=%s unexpected pipeline failure", job_id)
        job_manager.mark_failed(job_id, stage="pipeline", reason=redact(str(exc)))
    finally:
        attempt_sink.reset(sink_token)
