from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from backend.config import settings
from backend.services.model_router import Provider, call_with_fallback, models_to_try, redact, try_models

logger = logging.getLogger(__name__)

STAGE = "safety.content"

# Shown to the user; the category tells them *why* without echoing the prompt back.
CATEGORY_LABELS = {
    "sexual": "adult (18+) content",
    "minors": "sexual content involving minors",
    "deepfake": "deepfake or impersonation of a real person",
    "violence": "graphic violence or gore",
    "hate": "hate or harassment",
    "self_harm": "self-harm",
    "dangerous": "instructions for weapons, drugs or other harm",
    "other": "content that is not suitable for all audiences",
}

# Obvious, unambiguous terms only: this layer is instant, free and works with no API key at all.
# Anything subtler is left to the AI check below so legitimate topics (sex education, breast cancer
# awareness, war history) are not rejected by a keyword.
_LOCAL_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("minors", re.compile(r"\b(child|kid|minor|underage|teen|loli\w*)\W+(porn\w*|nude|naked|sex\w*|erotic)\b|\bchild\s+abuse\s+(video|material)\b|\bcsam\b", re.I)),
    ("sexual", re.compile(
        r"\bporn\w*\b|\bhentai\b|\bxxx\b|\bnsfw\b|\bonlyfans\b|\berotic\w*\b|\bsex\s*(scene|tape|video|act)s?\b|"
        r"\b18\s*\+|\badult\s+(video|content|film)s?\b|\bnude\s+(photo|pic|video|scene|girl|woman|man|body)s?\b|"
        r"\bnaked\s+(girl|woman|man|body|people|person)s?\b|\bstrip\s*tease\b|\bblowjob\b|\bfetish\b", re.I)),
    ("deepfake", re.compile(
        r"\bdeep\s*-?fakes?\b|\bface\s*-?swap\w*\b|\bfake\s+(video|audio|speech|voice|clip|statement)\s+(of|about|featuring)\b|"
        r"\bclone\s+(the\s+)?(voice|face)\s+of\b", re.I)),
    ("violence", re.compile(r"\bgore\b|\bbehead\w*\b|\bdismember\w*\b|\bsnuff\b|\btorture\s+(video|scene)s?\b|\bmutilat\w+\b", re.I)),
    ("self_harm", re.compile(r"\bhow\s+to\s+(kill|hurt|harm)\s+(myself|yourself|oneself)\b|\bsuicide\s+(method|way|guide)s?\b", re.I)),
    ("dangerous", re.compile(
        r"\bhow\s+to\s+(make|build|cook|synthesi[sz]e)\s+(a\s+)?(bomb|explosive|meth|methamphetamine|nerve\s+agent|ied)\b|"
        r"\bbuy\s+(illegal\s+)?(drugs|weapons)\s+online\b", re.I)),
]

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


@dataclass(frozen=True)
class SafetyVerdict:
    allowed: bool
    category: str = ""
    # "rules" (instant keyword layer) or "ai" (model check); empty when allowed.
    source: str = ""

    @property
    def message(self) -> str:
        if self.allowed:
            return ""
        label = CATEGORY_LABELS.get(self.category, CATEGORY_LABELS["other"])
        return (
            f"Not appropriate video: this idea looks like {label}. "
            "IdeaFeed only makes videos that are safe for all audiences, including kids. "
            "Try a different idea."
        )


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(_LEET)).strip()


def check_rules(text: str) -> SafetyVerdict:
    """Instant keyword screen. Needs no network and no key, so it works even if every AI provider is down."""
    for candidate in (text, _normalise(text)):
        for category, pattern in _LOCAL_RULES:
            if pattern.search(candidate):
                return SafetyVerdict(False, category, "rules")
    return SafetyVerdict(True)


_AI_SYSTEM = (
    "You are a strict content-safety reviewer for an app that turns a text idea into a short video "
    "that must be suitable for ALL audiences, including children. Reject ideas that ask for: "
    "sexual or 18+ content ('sexual'), anything sexual involving minors ('minors'), deepfakes, face swaps, "
    "voice cloning or fake footage/statements of a real person ('deepfake'), graphic violence or gore "
    "('violence'), hate or harassment ('hate'), self-harm ('self_harm'), or instructions for weapons, "
    "drugs or other serious harm ('dangerous'). Educational, news, history, health and safety topics "
    "are allowed when handled for a general audience. Reply with JSON only: "
    '{"allowed": true|false, "category": "<one of the names above, or empty>"}.'
)
_AI_TIMEOUT_SECONDS = 8.0


def _parse_verdict(raw: str) -> SafetyVerdict:
    match = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(match.group(0) if match else raw)
    if bool(data.get("allowed", True)):
        return SafetyVerdict(True)
    category = str(data.get("category") or "other").strip().lower()
    return SafetyVerdict(False, category if category in CATEGORY_LABELS else "other", "ai")


def _ask_gemini(text: str, model: str) -> SafetyVerdict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": f"Idea to review:\n{text[:1500]}"}]}],
        "systemInstruction": {"parts": [{"text": _AI_SYSTEM}]},
        "generationConfig": {"responseMimeType": "application/json"},
    }
    last: Exception | None = None
    for key in settings.gemini_key_pool:
        try:
            with httpx.Client(timeout=_AI_TIMEOUT_SECONDS) as client:
                response = client.post(url, json=payload, headers={"x-goog-api-key": key})
                response.raise_for_status()
                return _parse_verdict(response.json()["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as exc:  # noqa: BLE001 - next key
            last = exc
    raise last or RuntimeError("GEMINI_API_KEY not configured")


def _ask_groq(text: str, model: str) -> SafetyVerdict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _AI_SYSTEM},
            {"role": "user", "content": f"Idea to review:\n{text[:1500]}"},
        ],
        "response_format": {"type": "json_object"},
    }
    last: Exception | None = None
    for key in settings.groq_key_pool:
        try:
            with httpx.Client(timeout=_AI_TIMEOUT_SECONDS) as client:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {key}"},
                )
                response.raise_for_status()
                return _parse_verdict(response.json()["choices"][0]["message"]["content"])
        except Exception as exc:  # noqa: BLE001 - next key
            last = exc
    raise last or RuntimeError("GROQ_API_KEY not configured")


def check_ai(text: str) -> SafetyVerdict | None:
    """AI review through the usual provider chain. Returns None when no provider could answer."""
    providers = []
    if settings.gemini_key_pool:
        providers.append(Provider("gemini", lambda: try_models(
            lambda m: _ask_gemini(text, m), models_to_try(settings.gemini_model, settings.gemini_fallback_models)[:2])))
    if settings.groq_key_pool:
        providers.append(Provider("groq", lambda: try_models(
            lambda m: _ask_groq(text, m), models_to_try(settings.groq_model, settings.groq_fallback_models)[:2])))
    if not providers:
        return None
    try:
        return call_with_fallback(providers, stage=STAGE)
    except Exception as exc:  # noqa: BLE001 - the keyword layer already ran; an AI outage must not block creators
        logger.warning("content safety AI check unavailable, relying on keyword rules: %s", redact(str(exc))[:200])
        return None


def review(text: str) -> SafetyVerdict:
    """Is this idea fit for a video anyone (including a child) can watch?

    Layer 1, keyword rules: instant and offline. Layer 2, an AI reviewer for subtler cases; if no AI
    provider answers, layer 1's "allowed" stands so an outage never stops legitimate users."""
    verdict = check_rules(text)
    if not verdict.allowed:
        return verdict
    if not settings.content_safety_ai:
        return verdict
    return check_ai(text) or verdict
