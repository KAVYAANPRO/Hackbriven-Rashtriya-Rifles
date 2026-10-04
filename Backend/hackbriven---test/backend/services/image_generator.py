from __future__ import annotations

import base64
import hashlib
import io
import logging
import textwrap
import threading
from datetime import datetime, timedelta, timezone
import time
from pathlib import Path
from urllib.parse import quote

import httpx
from PIL import Image, ImageDraw, ImageFont

from backend.config import settings
from backend.services import framing
from backend.services.model_router import Provider, call_with_fallback

logger = logging.getLogger(__name__)

STAGE = "generation.image"

_POLLINATIONS_RETRYABLE_STATUS = {402, 429, 503}
_POLLINATIONS_MAX_ATTEMPTS = 4
_POLLINATIONS_RETRY_DELAY_SECONDS = 8.0

# A pipeline job calls Pollinations once per scene, back-to-back - live
# testing showed that alone is enough to trip its free-tier rate limit
# (confirmed: identical requests fail then succeed seconds apart with no
# code change). Space calls out proactively so a job's own request burst
# doesn't trigger the limit in the first place; the retry above still
# covers genuinely external contention (other users hitting the same pool).
_POLLINATIONS_MIN_INTERVAL_SECONDS = 10.0
_pollinations_pacing_lock = threading.Lock()
_pollinations_last_call_at = 0.0


def _pace_pollinations() -> None:
    global _pollinations_last_call_at
    with _pollinations_pacing_lock:
        now = time.monotonic()
        wait = _POLLINATIONS_MIN_INTERVAL_SECONDS - (now - _pollinations_last_call_at)
        if wait > 0:
            time.sleep(wait)
        _pollinations_last_call_at = time.monotonic()


# NVIDIA's hosted image models (live-confirmed with black-forest-labs/flux.1-dev,
# the configured default) only accept width/height from a fixed enumerated set,
# not our arbitrary 1080x1920 target - request the closest valid pair to our
# 9:16 aspect ratio, then center-crop to the exact target like the Pollinations
# path does, rather than assuming any model accepts arbitrary dimensions.
_NVIDIA_REQUEST_WIDTH = 768
_NVIDIA_REQUEST_HEIGHT = 1344


def _call_nvidia(prompt: str, out_path: Path) -> Path:
    if not settings.nvidia_api_key:
        raise RuntimeError("NVIDIA_API_KEY not configured")

    url = f"https://ai.api.nvidia.com/v1/genai/{settings.nvidia_image_model}"
    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Accept": "application/json",
    }
    payload = {
        "prompt": prompt,
        "width": _NVIDIA_REQUEST_WIDTH,
        "height": _NVIDIA_REQUEST_HEIGHT,
    }
    with httpx.Client(timeout=min(settings.provider_timeout_seconds, settings.nvidia_image_timeout_seconds)) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()

    image_b64 = body.get("image") or body["artifacts"][0]["base64"]
    image = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
    _save_framed(image, out_path)
    return out_path


def _center_crop(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    src_w, src_h = image.size
    scale = max(target_width / src_w, target_height / src_h)
    resized = image.resize((round(src_w * scale), round(src_h * scale)))
    rw, rh = resized.size
    left = (rw - target_width) // 2
    top = (rh - target_height) // 2
    return resized.crop((left, top, left + target_width, top + target_height))


def _call_pollinations(prompt: str, out_path: Path) -> Path:
    """Pollinations' free tier now only serves exact square (width == height)
    images with no `nologo` param - any other aspect ratio or the nologo
    flag returns 402 Payment Required (confirmed live, not documented
    anywhere at the time this was written). Request a square at our target
    height, then center-crop to the target vertical aspect ratio.

    Even square requests intermittently 402/429 under moderate call volume
    (live-confirmed: the exact same request failed, then succeeded seconds
    later with no code change) - a short retry-with-backoff absorbs that
    without escalating to the next provider in the chain unnecessarily.
    """
    size = settings.target_height
    encoded_prompt = quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={size}&height={size}"

    _pace_pollinations()

    content = b""
    last_error: Exception | None = None
    for attempt in range(1, _POLLINATIONS_MAX_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=settings.provider_timeout_seconds, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                content = response.content
            last_error = None
            break
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if status not in _POLLINATIONS_RETRYABLE_STATUS or attempt == _POLLINATIONS_MAX_ATTEMPTS:
                raise
            logger.warning(
                "pollinations attempt %s/%s got %s, retrying in %ss",
                attempt, _POLLINATIONS_MAX_ATTEMPTS, status, _POLLINATIONS_RETRY_DELAY_SECONDS,
            )
            time.sleep(_POLLINATIONS_RETRY_DELAY_SECONDS)

    if last_error is not None:
        raise last_error
    if not content:
        raise RuntimeError("pollinations returned empty image body")

    image = Image.open(io.BytesIO(content)).convert("RGB")
    # The free tier stamps a small "pollinations.ai" mark along the bottom edge; trim it off.
    image = image.crop((0, 0, image.width, int(image.height * 0.93)))
    _save_framed(image, out_path)
    return out_path


def _save_framed(image: Image.Image, out_path: Path) -> None:
    """Fit any generator output into the video frame (blurred-backdrop framing for
    squares, cover-crop for near-vertical images) and save it as the scene image."""
    framing.fit_to_frame(image, settings.target_width, settings.target_height).save(out_path, format="PNG")


# --- Cloudflare Workers AI (free tier, no card) ---

_CF_RETRYABLE = {429, 500, 502, 503, 504}

# Cloudflare's free tier is a daily neuron allowance that resets at 00:00 UTC. Once it is used up
# (error code 4006) every further call fails the same way until then, so remember it and stop
# calling instead of retrying every scene of every job.
_cf_quota_lock = threading.Lock()
_cf_quota_until: dict[str, datetime] = {}  # account id -> when its daily allowance comes back


class CloudflareQuotaExceeded(RuntimeError):
    pass


def _next_utc_midnight() -> datetime:
    now = datetime.now(timezone.utc)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _exhausted_accounts() -> dict[str, datetime]:
    now = datetime.now(timezone.utc)
    with _cf_quota_lock:
        for account_id in [a for a, until in _cf_quota_until.items() if now >= until]:
            del _cf_quota_until[account_id]
        return dict(_cf_quota_until)


def cloudflare_quota_exhausted_until() -> datetime | None:
    """When Cloudflare images come back, if EVERY configured account has used up today's allowance."""
    pool = [account_id for account_id, _ in settings.cloudflare_account_pool]
    exhausted = _exhausted_accounts()
    if not pool or any(account_id not in exhausted for account_id in pool):
        return None
    return min(exhausted[account_id] for account_id in pool)


def cloudflare_account_status() -> list[dict]:
    """Per-key availability for the admin view (ids masked, tokens never included). Keys on the same
    account share its allowance, so they go unavailable together."""
    exhausted = _exhausted_accounts()
    seen: dict[str, int] = {}
    status = []
    for account_id, _ in settings.cloudflare_account_pool:
        seen[account_id] = seen.get(account_id, 0) + 1
        status.append({
            "account": f"...{account_id[-4:]}",
            "key": seen[account_id],
            "available": account_id not in exhausted,
            "resets_at": exhausted[account_id].isoformat() if account_id in exhausted else None,
        })
    return status


def _mark_quota_exhausted(account_id: str) -> None:
    with _cf_quota_lock:
        _cf_quota_until[account_id] = _next_utc_midnight()


def reset_cloudflare_quota() -> None:
    with _cf_quota_lock:
        _cf_quota_until.clear()


def _is_quota_error(response: httpx.Response) -> bool:
    if response.status_code != 429:
        return False
    try:
        errors = (response.json() or {}).get("errors") or []
    except ValueError:
        return False
    return any(e.get("code") == 4006 or "daily free allocation" in str(e.get("message", "")) for e in errors)


def _is_prompt_rejected(exc: Exception) -> bool:
    """Cloudflare error 8007: the prompt tripped the content filter (it has false positives)."""
    response = getattr(exc, "response", None)
    if response is None or response.status_code != 400:
        return False
    try:
        errors = (response.json() or {}).get("errors") or []
    except ValueError:
        return False
    return any(e.get("code") == 8007 or "NSFW" in str(e.get("message", "")) for e in errors)


def _quota_message(until: datetime) -> str:
    return f"daily free image limit used up - resets at {until.strftime('%H:%M')} UTC"
_CF_ATTEMPTS = 3


def _post_with_retries(client: httpx.Client, url: str, payload: dict, headers: dict) -> httpx.Response:
    """Cloudflare is the primary (often only) image provider, so ride out short hiccups - rate
    limits, 5xx, timeouts - with a couple of backed-off retries before giving up on a scene."""
    last: Exception | None = None
    for attempt in range(1, _CF_ATTEMPTS + 1):
        try:
            response = client.post(url, json=payload, headers=headers)
            if _is_quota_error(response):
                raise CloudflareQuotaExceeded("daily free image limit used up for this account")
            if response.status_code not in _CF_RETRYABLE or attempt == _CF_ATTEMPTS:
                response.raise_for_status()
                return response
            last = httpx.HTTPStatusError(f"cloudflare returned {response.status_code}", request=response.request, response=response)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last = exc
            if attempt == _CF_ATTEMPTS:
                raise
        time.sleep(2.0 * attempt)
    raise last or RuntimeError("cloudflare request failed")



def _call_cloudflare(prompt: str, out_path: Path) -> Path:
    """Try every configured Cloudflare account in turn. An account whose daily allowance is used up is
    remembered and skipped until 00:00 UTC; only when all of them are spent (or failing) does the chain
    move on to the next provider."""
    pool = settings.cloudflare_account_pool
    if not pool:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not configured")
    until = cloudflare_quota_exhausted_until()
    if until is not None:
        raise CloudflareQuotaExceeded(_quota_message(until))

    last_error: Exception | None = None
    for account_id, token in pool:
        if account_id in _exhausted_accounts():  # re-checked: another key on this account may just have hit the limit
            continue
        headers = {"Authorization": f"Bearer {token}"}
        for model in settings.cloudflare_image_model_list:
            # FLUX.1 [schnell] takes only prompt + steps (more steps = finer detail, up to 8);
            # models that take a size get the portrait size the video wants.
            payload: dict = {"prompt": prompt[:2000]}
            if "flux-1-schnell" in model:
                payload["steps"] = max(1, min(8, int(settings.cloudflare_flux_steps)))
            else:
                payload["width"], payload["height"] = _NVIDIA_REQUEST_WIDTH, _NVIDIA_REQUEST_HEIGHT
            url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
            try:
                with httpx.Client(timeout=settings.provider_timeout_seconds * 2) as client:
                    response = _post_with_retries(client, url, payload, headers)
                    content_type = str(response.headers.get("content-type", ""))
                    if content_type.startswith("image/"):
                        raw = response.content  # some models stream the image bytes directly
                    else:
                        body = response.json()
                        encoded = (body.get("result") or {}).get("image") or body.get("image")
                        if not encoded:
                            raise RuntimeError(f"{model} returned no image: {body.get('errors')}")
                        raw = base64.b64decode(encoded)
                _save_framed(Image.open(io.BytesIO(raw)).convert("RGB"), out_path)
                return out_path
            except CloudflareQuotaExceeded as exc:
                # The allowance is per account: skip this account (all its models) until the reset.
                _mark_quota_exhausted(account_id)
                last_error = exc
                logger.warning("cloudflare account ...%s used up its daily allowance", account_id[-4:])
                break
            except Exception as exc:  # noqa: BLE001 - try the next model, then the next account
                if _is_prompt_rejected(exc):
                    # Cloudflare's safety filter judges the prompt, not the key - every account would
                    # refuse it too, so hand the scene straight to the next provider.
                    raise
                last_error = exc
                logger.warning("cloudflare account ...%s model %s failed: %s", account_id[-4:], model, exc)

    until = cloudflare_quota_exhausted_until()
    if until is not None:
        raise CloudflareQuotaExceeded(_quota_message(until))
    raise last_error or RuntimeError("no Cloudflare image model configured")


# --- OpenRouter (/api/v1/images) - needs a funded OpenRouter balance ---


def _call_openrouter_image(prompt: str, out_path: Path) -> Path:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY not configured")

    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    last_error: Exception | None = None
    for model in settings.openrouter_image_model_list:
        body = {"model": model, "prompt": prompt[:2000], "aspect_ratio": "9:16", "output_format": "png"}
        try:
            with httpx.Client(timeout=settings.provider_timeout_seconds * 2) as client:
                response = client.post("https://openrouter.ai/api/v1/images", json=body, headers=headers)
                if response.status_code == 400:
                    # This provider may not take an aspect ratio; ask for an explicit portrait size instead.
                    body = {
                        "model": model,
                        "prompt": prompt[:2000],
                        "size": f"{_NVIDIA_REQUEST_WIDTH}x{_NVIDIA_REQUEST_HEIGHT}",
                    }
                    response = client.post("https://openrouter.ai/api/v1/images", json=body, headers=headers)
                response.raise_for_status()
                data = response.json().get("data") or []
                if not data or not data[0].get("b64_json"):
                    raise RuntimeError(f"{model} returned no image")
                raw = base64.b64decode(data[0]["b64_json"])
            _save_framed(Image.open(io.BytesIO(raw)).convert("RGB"), out_path)
            return out_path
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code == 402:
                break  # no credit: the next model would be refused the same way
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise last_error or RuntimeError("no OpenRouter image model configured")


def _prompt_to_gradient(prompt: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    top = (80 + digest[0] % 120, 80 + digest[1] % 120, 80 + digest[2] % 120)
    bottom = tuple(max(0, c - 70) for c in top)
    return top, bottom


def _generate_placeholder(prompt: str, out_path: Path) -> Path:
    """Last-resort, fully offline image: a gradient card (color deterministically
    derived from the prompt, so scenes stay visually distinct) with the scene's
    image prompt rendered as centered text. Guarantees the Generation stage can
    never hard-fail for lack of a working external image API - same role as
    story_engine's local_template for the Intelligence stage."""
    width, height = settings.target_width, settings.target_height
    top, bottom = _prompt_to_gradient(prompt)

    image = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=row)

    try:
        font = ImageFont.truetype("arial.ttf", 56)
    except OSError:
        font = ImageFont.load_default()

    wrapped = textwrap.fill(prompt, width=24)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=14, align="center")
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.multiline_text(
        ((width - text_w) // 2, (height - text_h) // 2),
        wrapped,
        font=font,
        fill=(255, 255, 255),
        align="center",
        spacing=14,
        stroke_width=3,
        stroke_fill=(0, 0, 0),
    )

    image.save(out_path, format="PNG")
    return out_path


def generate_image(prompt: str, out_path: Path) -> Path:
    """Best available image for one scene. Providers that aren't configured are left out of the
    chain entirely (so the job's provider history only shows real attempts); ones that fail are
    put on a cool-down so a hung or unfunded provider can't tax every scene of the job."""
    cooldown = settings.provider_cooldown_seconds
    builders = {
        # Cloudflare retries internally and is usually the only provider, so it is never cooled down.
        "cloudflare": lambda: settings.has_cloudflare
        and Provider("cloudflare", lambda: _call_cloudflare(prompt, out_path)),
        "openrouter": lambda: bool(settings.openrouter_api_key and settings.openrouter_image_model_list)
        and Provider("openrouter", lambda: _call_openrouter_image(prompt, out_path), cooldown),
        "nvidia": lambda: bool(settings.nvidia_api_key)
        and Provider("nvidia_sd35", lambda: _call_nvidia(prompt, out_path), cooldown),
        "pollinations": lambda: settings.image_use_pollinations
        and Provider("pollinations", lambda: _call_pollinations(prompt, out_path)),
    }
    providers: list[Provider] = []
    for name in settings.image_provider_list:
        provider = builders.get(name, lambda: None)()
        if provider:
            providers.append(provider)
    # Local title card: not an AI service, only so a job never dies for want of one image.
    providers.append(Provider("local_placeholder", lambda: _generate_placeholder(prompt, out_path)))
    return call_with_fallback(providers, stage=STAGE)
