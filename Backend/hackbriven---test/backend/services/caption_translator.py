from __future__ import annotations

import json
import logging
import re

import httpx

from backend.config import settings
from backend.services.model_router import Provider, call_with_fallback

logger = logging.getLogger(__name__)

STAGE = "generation.caption_translation"

_TARGET_NAME = {
    "en": "English",
    "hi": "Hindi written in Devanagari script",
    "hinglish": "Hinglish (Hindi-English mix written in Latin/Roman script)",
}


def _prompt(lines: list[str], target: str) -> str:
    return (
        f"Translate each line into {_TARGET_NAME[target]} for short on-screen video captions. "
        "Keep the meaning, keep it natural and short. Return ONLY a JSON array of strings with exactly "
        f"{len(lines)} items, in the same order.\n\n" + json.dumps(lines, ensure_ascii=False)
    )


def _parse(text: str, expected: int) -> list[str]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise RuntimeError("translation returned no JSON array")
    items = json.loads(match.group(0))
    if not isinstance(items, list) or len(items) != expected or not all(isinstance(i, str) for i in items):
        raise RuntimeError("translation returned the wrong number of lines")
    return [" ".join(i.split()) for i in items]


def _gemini(prompt: str) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
        response = client.post(
            url, json={"contents": [{"parts": [{"text": prompt}]}]}, headers={"x-goog-api-key": settings.gemini_api_key}
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(prompt: str) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY not configured")
    with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
        response = client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={"model": settings.groq_model, "messages": [{"role": "user", "content": prompt}]},
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def translate_lines(lines: list[str], target: str) -> list[str]:
    """Translate caption lines (one per scene). On any failure the original lines are returned, so
    captions fall back to the narration's language instead of breaking the video."""
    if not lines or target not in _TARGET_NAME:
        return lines
    prompt = _prompt(lines, target)
    try:
        return call_with_fallback(
            [
                Provider("gemini", lambda: _parse(_gemini(prompt), len(lines))),
                Provider("groq", lambda: _parse(_groq(prompt), len(lines))),
            ],
            stage=STAGE,
        )
    except Exception as exc:  # noqa: BLE001 - untranslated captions beat no video
        logger.warning("caption translation to %s failed, keeping the original language: %s", target, exc)
        return lines
