from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_resolved_paths: tuple[str, str] | None = None


class FfmpegNotAvailableError(RuntimeError):
    pass


def _resolve_binaries() -> tuple[str, str]:
    """Find ffmpeg/ffprobe: prefer PATH, fall back to the static-ffmpeg pip
    package (downloads a static build into a user-writable cache on first
    use, no admin rights needed).
    """
    global _resolved_paths
    if _resolved_paths is not None:
        return _resolved_paths

    on_path_ffmpeg = shutil.which("ffmpeg")
    on_path_ffprobe = shutil.which("ffprobe")
    if on_path_ffmpeg and on_path_ffprobe:
        _resolved_paths = (on_path_ffmpeg, on_path_ffprobe)
        return _resolved_paths

    try:
        import static_ffmpeg

        ffmpeg_path, ffprobe_path = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
    except Exception as exc:  # noqa: BLE001 - any resolution failure means "not available"
        raise FfmpegNotAvailableError(
            "ffmpeg/ffprobe not found on PATH and the static-ffmpeg fallback "
            f"failed: {exc}"
        ) from exc

    _resolved_paths = (ffmpeg_path, ffprobe_path)
    return _resolved_paths


def ffmpeg_path() -> str:
    path, _ = _resolve_binaries()
    return path


def run_ffmpeg(args: list[str], *, stage: str) -> None:
    ffmpeg_path, _ = _resolve_binaries()
    cmd = [ffmpeg_path, "-y", "-loglevel", "error", *args]
    logger.info("stage=%s running: %s", stage, " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (stage={stage}): {result.stderr.strip()}")


def probe(path: Path) -> dict:
    _, ffprobe_path = _resolve_binaries()
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    return json.loads(result.stdout)


def get_duration_seconds(path: Path) -> float:
    data = probe(path)
    duration = data.get("format", {}).get("duration")
    if duration is None:
        raise RuntimeError(f"ffprobe returned no duration for {path}")
    return float(duration)
