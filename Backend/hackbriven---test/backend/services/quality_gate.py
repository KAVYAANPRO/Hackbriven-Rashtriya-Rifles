from __future__ import annotations

import logging
from pathlib import Path

from backend.config import settings
from backend.models.schemas import QualityReport
from backend.utils.ffmpeg_utils import probe

logger = logging.getLogger(__name__)

STAGE = "validation.quality_gate"

_DURATION_TOLERANCE_SECONDS = 1.5


def check(
    video_path: Path,
    expected_duration_seconds: float,
    *,
    expected_width: int | None = None,
    expected_height: int | None = None,
) -> QualityReport:
    reasons: list[str] = []

    if not video_path.exists() or video_path.stat().st_size == 0:
        return QualityReport(passed=False, reasons=["output file missing or empty"])

    data = probe(video_path)
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width = video_stream.get("width") if video_stream else None
    height = video_stream.get("height") if video_stream else None
    duration_raw = data.get("format", {}).get("duration")
    duration = float(duration_raw) if duration_raw is not None else None
    has_audio = audio_stream is not None

    if video_stream is None:
        reasons.append("no video stream found")
    else:
        want_w = expected_width or settings.target_width
        want_h = expected_height or settings.target_height
        if width != want_w or height != want_h:
            reasons.append(f"resolution {width}x{height} != expected {want_w}x{want_h}")

    if duration is None:
        reasons.append("could not determine duration")
    elif abs(duration - expected_duration_seconds) > _DURATION_TOLERANCE_SECONDS:
        reasons.append(
            f"duration {duration:.2f}s outside tolerance of "
            f"{expected_duration_seconds:.2f}s +/- {_DURATION_TOLERANCE_SECONDS}s"
        )

    if not has_audio:
        reasons.append("no audio track found")
    elif audio_stream is not None:
        channels = audio_stream.get("channels", 0)
        if channels == 0:
            reasons.append("audio track has zero channels")

    return QualityReport(
        passed=not reasons,
        width=width,
        height=height,
        duration_seconds=duration,
        has_audio_track=has_audio,
        reasons=reasons,
    )
