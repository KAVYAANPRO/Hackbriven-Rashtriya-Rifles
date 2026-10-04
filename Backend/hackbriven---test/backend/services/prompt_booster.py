from __future__ import annotations

import logging
import re

import httpx

from backend.config import settings
from backend.core.exceptions import AllProvidersFailedError
from backend.models.schemas import Language
from backend.services import styles
from backend.services.model_router import Provider, call_with_fallback, models_to_try, try_models

logger = logging.getLogger(__name__)

STAGE = "intelligence.prompt_boost"

# The AI prompter. It has to do more than "make it longer": keep what the user actually asked for
# (named people, teams, the 'versus' angle), give the video a structure, and describe visuals an
# image model can render without needing anyone's real face.
_INSTRUCTION = (
    "You are a creative director for short vertical videos (Reels, Shorts, TikTok). Rewrite the user's rough "
    "idea into one rich, production-ready prompt for an AI video generator.\n"
    "Rules:\n"
    "1. Keep every named person, team, brand, place and product EXACTLY as the user wrote it, and keep their "
    "angle. 'A vs B' or 'A versus B' means a head-to-head comparison of A and B, never a video about only one "
    "of them. 'Why is X better than Y' means argue X's case fairly against Y.\n"
    "2. Never invent statistics, records, dates or quotes. If numbers would help, tell the video to use only "
    "well-known facts or to hedge ('many fans argue').\n"
    "3. Structure it: a hook for the first 3 seconds, 3 to 4 story beats, and a closing line that invites "
    "comments. Name the pacing (about 30 to 40 seconds).\n"
    "4. Describe visuals an image generator can draw: settings, lighting, camera moves, colours, objects. For real "
    "people describe their cars, helmets, jerseys, trophies, silhouettes, crowds or iconic places instead of "
    "their faces. Image models do not know names, so spell out each subject's visual identity (team and car "
    "colours and livery, race numbers, kit colours, flags, the specific venue). No text or logos inside images.\n"
    "5. Write 4 to 6 sentences in the SAME language and script as the idea (Hindi stays Hindi in Devanagari, "
    "Hinglish stays Hinglish in Latin letters, English stays English).\n"
    "6. Return ONLY the rewritten prompt: no headings, bullets, quotes or commentary."
)

_LANGUAGE_HINT = {
    Language.EN: "The video will be narrated in English.",
    Language.HI: "Write the prompt in Hindi using Devanagari script. The video will be narrated in Hindi.",
    Language.HINGLISH: (
        "Write the prompt in Hinglish (Hindi-English mix as spoken in urban India) using ONLY Latin/English "
        "letters, never Devanagari. The video will be narrated in Hinglish."
    ),
}


def _system_prompt(language: Language | None, style: str = "auto", style_prompt: str | None = None) -> str:
    parts = [_INSTRUCTION]
    if language:
        parts.append(_LANGUAGE_HINT[language])
    tone = styles.tone_for(style, style_prompt)
    visual = styles.visual_for(style, style_prompt)
    if tone or visual:
        label = (styles.get(style).label if styles.get(style) else "custom")
        parts.append(f"Requested video style: {label}. {tone} Visual direction: {visual}".strip())
    return "\n".join(parts)


def clean_output(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    return re.sub(r"^[\"“”']+|[\"“”']+$", "", text).strip()


def local_enhance(prompt: str) -> str:
    """Deterministic, offline expansion. NOT AI-written - callers must report
    it as source "local"."""
    idea = re.sub(r"[.!?…।]+$", "", re.sub(r"\s+", " ", prompt.strip()))
    return " ".join(
        [
            f"Open with a hook in the first three seconds that makes people stop scrolling: {idea}.",
            "Build it in three beats: the surprising claim, one concrete example that proves it, and a clear takeaway or twist at the end.",
            "Visual style: close, high-contrast shots in natural colour, a new shot every two to three seconds, bold on-screen captions.",
            "Pacing: fast and conversational, about 30 to 40 seconds, finishing on a line that invites a comment.",
        ]
    )


def _require_text(text: str, provider: str) -> str:
    cleaned = clean_output(text or "")
    if not cleaned:
        raise RuntimeError(f"{provider} returned an empty answer")
    return cleaned


def _call_gemini(
    prompt: str, language: Language | None, style: str = "auto", style_prompt: str | None = None, model: str | None = None
) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model or settings.gemini_model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": _system_prompt(language, style, style_prompt)}]},
        "contents": [{"parts": [{"text": f"Idea:\n{prompt}"}]}],
    }
    with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
        response = client.post(url, json=payload, headers={"x-goog-api-key": settings.gemini_api_key})
        response.raise_for_status()
        body = response.json()
    return _require_text(body["candidates"][0]["content"]["parts"][0]["text"], "gemini")


def _call_chat(
    url: str, api_key: str, model: str, prompt: str, language: Language | None, name: str,
    style: str = "auto", style_prompt: str | None = None,
) -> str:
    if not api_key:
        raise RuntimeError(f"{name.upper()}_API_KEY not configured")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt(language, style, style_prompt)},
            {"role": "user", "content": f"Idea:\n{prompt}"},
        ],
    }
    with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
        response = client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
        body = response.json()
    return _require_text(body["choices"][0]["message"]["content"], name)


def boost(
    prompt: str, language: Language | None = None, style: str = "auto", style_prompt: str | None = None
) -> tuple[str, str]:
    """Rewrite a rough idea into a richer video prompt. Returns (text, source)
    where source names the provider that actually answered - "local" when the
    whole AI chain failed or isn't configured (never presented as AI)."""
    clean = prompt.strip()
    providers = [
        Provider(
            name="groq",
            call=lambda: (
                "groq",
                try_models(
                    lambda m: _call_chat(
                        "https://api.groq.com/openai/v1/chat/completions",
                        settings.groq_api_key, m, clean, language, "groq", style, style_prompt,
                    ),
                    models_to_try(settings.groq_model, settings.groq_fallback_models),
                ),
            ),
        ),
        Provider(
            name="gemini",
            call=lambda: (
                "gemini",
                try_models(
                    lambda m: _call_gemini(clean, language, style, style_prompt, model=m),
                    models_to_try(settings.gemini_model, settings.gemini_fallback_models),
                ),
            ),
        ),
        Provider(
            name="openrouter",
            call=lambda: (
                "openrouter",
                try_models(
                    lambda m: _call_chat(
                        "https://openrouter.ai/api/v1/chat/completions",
                        settings.openrouter_api_key, m, clean, language, "openrouter", style, style_prompt,
                    ),
                    models_to_try(settings.openrouter_model, settings.openrouter_fallback_models),
                ),
            ),
        ),
        Provider(name="local", call=lambda: ("local", local_enhance(clean))),
    ]
    try:
        source, text = call_with_fallback(providers, stage=STAGE)
    except AllProvidersFailedError:  # unreachable while "local" is last, kept as a safety net
        return local_enhance(clean), "local"
    return text, source
