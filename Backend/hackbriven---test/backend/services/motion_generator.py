from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

import httpx

from backend.config import settings
from backend.services.model_router import Provider, call_with_fallback

logger = logging.getLogger(__name__)

STAGE = "composition.motion"

_POLL_INTERVAL_SECONDS = 5.0
_POLL_TIMEOUT_SECONDS = 180.0


class MotionGenerationError(RuntimeError):
    pass


# --- 8scale.com (Wan 2.2 14B image-to-video) ---
# Tried first: 10 free generations per key, no card, no upload step needed
# (accepts the image as a base64 data URI directly in the job payload).

_EIGHTSCALE_BASE = "https://8scale.run"
_EIGHTSCALE_ALLOWED_SECONDS = (3, 5)


def _eightscale_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _call_eightscale(image_path: Path, prompt: str, duration_seconds: float, out_path: Path, *, api_key: str) -> Path:
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    # 8scale only accepts a fixed set of durations, not an arbitrary float -
    # pick the closest allowed value; video_composer normalizes the result
    # to the pipeline's exact needed duration afterward regardless.
    seconds = min(_EIGHTSCALE_ALLOWED_SECONDS, key=lambda s: abs(s - duration_seconds))
    payload = {
        "prompt": prompt,
        "resolution": settings.eightscale_resolution,
        "aspect_ratio": "9:16",
        "seconds": seconds,
        "image": f"data:image/png;base64,{image_b64}",
    }
    url = f"{_EIGHTSCALE_BASE}/{settings.eightscale_model}"

    with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
        response = client.post(url, json=payload, headers=_eightscale_headers(api_key))
        response.raise_for_status()
        request_id = response.json()["requestId"]

        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
        download_url = None
        while time.monotonic() < deadline:
            status_response = client.get(f"{_EIGHTSCALE_BASE}/status/{request_id}", headers=_eightscale_headers(api_key))
            status_response.raise_for_status()
            data = status_response.json()
            status = data.get("status")

            if status == "COMPLETED":
                download_url = data.get("output")
                if not download_url:
                    raise MotionGenerationError(f"8scale job {request_id} completed with no output url")
                break
            if status in ("FAILED", "CANCELLED"):
                raise MotionGenerationError(f"8scale job {request_id} ended with status {status}")

            time.sleep(_POLL_INTERVAL_SECONDS)
        else:
            raise MotionGenerationError(f"8scale job {request_id} did not complete within {_POLL_TIMEOUT_SECONDS}s")

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        download_response = client.get(download_url)
        download_response.raise_for_status()
        if not download_response.content:
            raise MotionGenerationError(f"8scale job {request_id} returned an empty video body")
        out_path.write_bytes(download_response.content)

    return out_path


# --- Magic Hour ---

_MAGIC_HOUR_BASE = "https://api.magichour.ai/v1"


def _magic_hour_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _magic_hour_upload_image(client: httpx.Client, image_path: Path, api_key: str) -> str:
    response = client.post(
        f"{_MAGIC_HOUR_BASE}/files/upload-urls",
        json={"items": [{"extension": "png", "type": "image"}]},
        headers=_magic_hour_headers(api_key),
    )
    response.raise_for_status()
    item = response.json()["items"][0]
    upload_url, file_path = item["upload_url"], item["file_path"]

    put_response = client.put(upload_url, content=image_path.read_bytes(), headers={"Content-Type": "image/png"})
    put_response.raise_for_status()

    return file_path


def _magic_hour_create_job(
    client: httpx.Client, uploaded_file_path: str, prompt: str, duration_seconds: float, api_key: str
) -> str:
    end_seconds = max(1, min(60, round(duration_seconds)))
    payload = {
        "end_seconds": end_seconds,
        "resolution": settings.magic_hour_resolution,
        "style": {"prompt": prompt},
        "assets": {"image_file_path": uploaded_file_path},
    }
    response = client.post(f"{_MAGIC_HOUR_BASE}/image-to-video", json=payload, headers=_magic_hour_headers(api_key))
    response.raise_for_status()
    return response.json()["id"]


def _magic_hour_poll_until_complete(client: httpx.Client, job_id: str, api_key: str) -> str:
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = client.get(f"{_MAGIC_HOUR_BASE}/video-projects/{job_id}", headers=_magic_hour_headers(api_key))
        response.raise_for_status()
        data = response.json()
        status = data.get("status")

        if status == "complete":
            download = data.get("download") or {}
            url = download.get("url")
            if not url:
                raise MotionGenerationError(f"magic hour job {job_id} completed with no download url")
            return url
        if status in ("error", "failed"):
            raise MotionGenerationError(f"magic hour job {job_id} failed: {data.get('error')}")

        time.sleep(_POLL_INTERVAL_SECONDS)

    raise MotionGenerationError(f"magic hour job {job_id} did not complete within {_POLL_TIMEOUT_SECONDS}s")


def _call_magic_hour(image_path: Path, prompt: str, duration_seconds: float, out_path: Path, *, api_key: str) -> Path:
    with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
        uploaded_file_path = _magic_hour_upload_image(client, image_path, api_key)
        job_id = _magic_hour_create_job(client, uploaded_file_path, prompt, duration_seconds, api_key)
        download_url = _magic_hour_poll_until_complete(client, job_id, api_key)

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(download_url)
        response.raise_for_status()
        if not response.content:
            raise MotionGenerationError(f"magic hour job {job_id} returned an empty video body")
        out_path.write_bytes(response.content)

    return out_path


def generate_motion_clip(image_path: Path, prompt: str, duration_seconds: float, out_path: Path) -> Path:
    """Real generative image-to-video, tried across providers in order
    (8scale first - genuinely free right now; Magic Hour second). Each
    provider's free tier is small per account, so every key in its pool
    (EIGHTSCALE_API_KEYS / MAGIC_HOUR_API_KEYS, one per account) is tried
    in turn before moving to the next provider - exhausting one account's
    quota just rotates to the next account, not to Ken Burns. Returns the
    raw downloaded clip at whatever resolution/fps/duration the provider
    produced - callers must normalize it to match the rest of the
    pipeline's clips before splicing it into the crossfade timeline.
    """
    eightscale_keys = settings.eightscale_key_pool
    magic_hour_keys = settings.magic_hour_key_pool

    providers = [
        Provider(
            name=f"eightscale[{i + 1}/{len(eightscale_keys)}]",
            call=lambda key=key: _call_eightscale(image_path, prompt, duration_seconds, out_path, api_key=key),
        )
        for i, key in enumerate(eightscale_keys)
    ] + [
        Provider(
            name=f"magic_hour[{i + 1}/{len(magic_hour_keys)}]",
            call=lambda key=key: _call_magic_hour(image_path, prompt, duration_seconds, out_path, api_key=key),
        )
        for i, key in enumerate(magic_hour_keys)
    ]
    return call_with_fallback(providers, stage=STAGE)
