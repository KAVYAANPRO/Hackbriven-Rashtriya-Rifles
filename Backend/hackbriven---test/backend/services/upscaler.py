from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

import httpx

from backend.config import settings
from backend.core.exceptions import PipelineError
from backend.services.model_router import Provider, call_with_fallback
from backend.utils.ffmpeg_utils import probe, run_ffmpeg

logger = logging.getLogger(__name__)

STAGE = "composition.enhance"

"""Server-side resolution enhancement. Nothing here is visible to the end user: the UI only
offers a resolution ("4K"), and the job's provider history names the step neutrally
("enhancer").

  * `enhance_video` - the 4K delivery: an AI video upscaler when one is configured and funded
    (fal.ai Topaz Video Upscale), otherwise a local high-quality ffmpeg resize + sharpen, so
    the requested resolution is always met.
  * `enhance_clip`  - motion clips from the image-to-video providers are only 480p; upscale
    them before they are spliced into the timeline. AI upscaler only (a plain resize happens
    anyway during normalisation), and silently skipped when unavailable.
"""

_FAL_QUEUE = "https://queue.fal.run"
_POLL_SECONDS = 4.0


def _fal_headers() -> dict:
    return {"Authorization": f"Key {settings.fal_api_key}"}


_FAL_BLOCKED_STATUS = {401, 402, 403}
_FAL_BLOCKED_SECONDS = 3600.0
_CLIP_TIMEOUT_SECONDS = 150.0
_fal_blocked_until = 0.0


def _fal_blocked() -> bool:
    return _fal_blocked_until > time.monotonic()


def _fal_upscale(src: Path, dst: Path, factor: float, timeout: float | None = None) -> Path:
    """Run a video through fal.ai's queue API; an unfunded/blocked key disables it for an hour."""
    global _fal_blocked_until
    if _fal_blocked():
        raise RuntimeError("enhancement service unavailable (account blocked or out of credit)")
    try:
        return _fal_upscale_once(src, dst, factor, timeout)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in _FAL_BLOCKED_STATUS:
            _fal_blocked_until = time.monotonic() + _FAL_BLOCKED_SECONDS
            logger.warning("enhancer rejected (%s); using local scaling for the next hour", exc.response.status_code)
        raise


def _fal_upscale_once(src: Path, dst: Path, factor: float, timeout: float | None) -> Path:
    if not settings.fal_api_key:
        raise RuntimeError("no enhancement service configured")

    video_uri = "data:video/mp4;base64," + base64.b64encode(src.read_bytes()).decode("ascii")
    payload = {"video_url": video_uri, "upscale_factor": factor, "H264_output": True}
    endpoint = settings.upscale_fal_endpoint

    with httpx.Client(timeout=120.0) as client:
        submitted = client.post(f"{_FAL_QUEUE}/{endpoint}", json=payload, headers=_fal_headers())
        submitted.raise_for_status()
        info = submitted.json()
        status_url, response_url = info["status_url"], info["response_url"]

        deadline = time.monotonic() + (timeout if timeout is not None else settings.upscale_timeout_seconds)
        while True:
            status = client.get(status_url, headers=_fal_headers())
            status.raise_for_status()
            state = status.json().get("status")
            if state == "COMPLETED":
                break
            if state not in ("IN_QUEUE", "IN_PROGRESS"):
                raise RuntimeError(f"enhancement ended with status {state}")
            if time.monotonic() > deadline:
                raise RuntimeError("enhancement timed out")
            time.sleep(_POLL_SECONDS)

        result = client.get(response_url, headers=_fal_headers())
        result.raise_for_status()
        video = (result.json().get("video") or {}).get("url")
        if not video:
            raise RuntimeError("enhancement returned no video")
        download = client.get(video, follow_redirects=True, timeout=300.0)
        download.raise_for_status()
        if not download.content:
            raise RuntimeError("enhancement returned an empty file")
        dst.write_bytes(download.content)
    return dst


def _ffmpeg_resize(src: Path, dst: Path, width: int, height: int) -> Path:
    """Fallback: Lanczos resize with a light sharpen pass, audio copied untouched."""
    run_ffmpeg(
        [
            "-i", str(src),
            "-vf", f"scale={width}:{height}:flags=lanczos,unsharp=5:5:0.6:3:3:0.3,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(dst),
        ],
        stage=f"{STAGE}.resize",
    )
    return dst


def _dimensions(path: Path) -> tuple[int, int]:
    stream = next(s for s in probe(path).get("streams", []) if s.get("codec_type") == "video")
    return int(stream["width"]), int(stream["height"])


def enhance_video(master: Path, dst: Path, *, width: int, height: int) -> Path:
    """Produce `dst` at exactly width x height from the 1080p master."""
    src_w, _ = _dimensions(master)
    tmp = dst.with_suffix(".enh.mp4")

    def ai() -> Path:
        _fal_upscale(master, tmp, factor=max(1.0, width / src_w))
        # The service may drop the audio or land a few pixels off: take the audio from the master
        # and force the exact frame size.
        run_ffmpeg(
            [
                "-i", str(tmp), "-i", str(master),
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", f"scale={width}:{height}:flags=lanczos,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "copy", "-shortest",
                "-movflags", "+faststart",
                str(dst),
            ],
            stage=f"{STAGE}.mux",
        )
        return dst

    providers = []
    if settings.enhancer_enabled and settings.fal_api_key and not _fal_blocked():
        providers.append(Provider("enhancer", ai, settings.provider_cooldown_seconds))
    providers.append(Provider("local_scale", lambda: _ffmpeg_resize(master, dst, width, height)))
    try:
        return call_with_fallback(providers, stage=STAGE)
    except PipelineError:
        raise
    finally:
        tmp.unlink(missing_ok=True)


def enhance_clip(raw: Path) -> Path | None:
    """Upscale a 480p motion clip in place. Returns the enhanced path, or None when no
    enhancer is available/funded (callers then just use the raw clip)."""
    if not (settings.enhancer_enabled and settings.enhance_motion_clips and settings.fal_api_key) or _fal_blocked():
        return None
    out = raw.with_name(raw.stem + ".enh.mp4")
    try:
        call_with_fallback(
            [
                Provider(
                    "enhancer",
                    lambda: _fal_upscale(raw, out, factor=2.0, timeout=_CLIP_TIMEOUT_SECONDS),
                    settings.provider_cooldown_seconds,
                )
            ],
            stage=f"{STAGE}.clip",
        )
    except PipelineError as exc:
        logger.warning("motion clip enhancement skipped: %s", exc.reason)
        out.unlink(missing_ok=True)
        return None
    return out
