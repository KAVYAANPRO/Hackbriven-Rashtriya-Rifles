from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job_id() -> str:
    return uuid.uuid4().hex[:12]


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING_INTELLIGENCE = "running_intelligence"
    RUNNING_GENERATION = "running_generation"
    RUNNING_COMPOSITION = "running_composition"
    RUNNING_VALIDATION = "running_validation"
    DONE = "done"  # rendered + quality-passed; equivalent to the PRD's "needs_review" - awaits approve()
    FAILED = "failed"
    CANCELLED = "cancelled"
    APPROVED = "approved"  # approve() called on a DONE job; only an APPROVED job may publish()
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PUBLISH_FAILED = "publish_failed"
    MANUAL_HANDOFF = "manual_handoff"  # no official Qoneqt publishing API exists - never claim PUBLISHED


class MotionTier(str, Enum):
    """How much real generative AI motion (Magic Hour, credit-metered) a job
    uses versus free Ken Burns pan/zoom."""

    MAX = "max"  # every scene attempts real motion
    BALANCED = "balanced"  # settings.magic_hour_max_scenes_per_job scenes (default)
    BASIC = "basic"  # Ken Burns only, zero credits spent


class Language(str, Enum):
    """Script + narration language. Changes both what the LLM is asked to
    write and which edge-tts voice reads it - feeding English TTS a
    Devanagari script (or vice versa) mispronounces badly, so these two
    must always move together, not be picked independently."""

    EN = "en"
    HI = "hi"  # Hindi, Devanagari script
    HINGLISH = "hinglish"  # Hindi-English code-switched, Latin script


class Scene(BaseModel):
    index: int
    narration: str
    image_prompt: str
    duration_seconds: float = Field(gt=0)
    mood: str = "neutral"


class Script(BaseModel):
    topic: str
    hook: str
    mood: str = "neutral"
    scenes: list[Scene]

    @property
    def total_duration_seconds(self) -> float:
        return sum(s.duration_seconds for s in self.scenes)


class ScenePlan(BaseModel):
    index: int
    narration: str
    image_prompt: str
    duration_seconds: float
    start_offset_seconds: float
    end_offset_seconds: float


class ScenePlanSet(BaseModel):
    topic: str
    hook: str
    scenes: list[ScenePlan]

    @property
    def total_duration_seconds(self) -> float:
        if not self.scenes:
            return 0.0
        return self.scenes[-1].end_offset_seconds


class SceneAssets(BaseModel):
    index: int
    image_path: str
    audio_path: str
    caption_words: list["CaptionWord"] = Field(default_factory=list)
    duration_seconds: float
    image_prompt: str = ""


class CaptionWord(BaseModel):
    word: str
    start_seconds: float
    end_seconds: float


class QualityReport(BaseModel):
    passed: bool
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    has_audio_track: bool | None = None
    reasons: list[str] = Field(default_factory=list)


class StageTimestamp(BaseModel):
    stage: str
    status: str
    at: datetime = Field(default_factory=_now)


class ProviderEvent(BaseModel):
    """One real attempt by one provider inside a stage's fallback chain, in
    the order it happened - this is what makes the "AI orchestra" reroute
    visible as fact instead of a simulation."""

    stage: str
    provider: str
    ok: bool
    error: str | None = None
    at: datetime = Field(default_factory=_now)


class Job(BaseModel):
    id: str = Field(default_factory=_job_id)
    owner: str | None = None  # account email; None = the anonymous/legacy "default" account
    reference_images: list[str] = Field(default_factory=list)  # upload ids used as the first scenes' visuals
    style: str = "auto"  # preset id from services/styles.py
    style_prompt: str | None = None  # only for style == "custom"
    resolution: str = "1080p"  # delivery resolution id from core/plans.py
    provider_events: list[ProviderEvent] = Field(default_factory=list)
    topic: str
    language: Language = Language.EN
    motion_tier: MotionTier = MotionTier.BALANCED
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    history: list[StageTimestamp] = Field(default_factory=list)
    script: Script | None = None
    scene_plan: ScenePlanSet | None = None
    quality_report: QualityReport | None = None
    result_path: str | None = None
    error_stage: str | None = None
    error_reason: str | None = None
    idempotency_key: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    published_at: datetime | None = None
    publish_error: str | None = None
    manual_handoff_path: str | None = None
    manual_handoff_note: str | None = None

    def touch(self) -> None:
        self.updated_at = _now()


SceneAssets.model_rebuild()
