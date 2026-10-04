from __future__ import annotations

import json
import logging

import httpx

from backend.config import settings
from backend.core.exceptions import InvalidScriptError
from backend.models.schemas import Language, Script
from backend.services import styles
from backend.services.model_router import Provider, call_with_fallback, models_to_try, try_models

logger = logging.getLogger(__name__)

STAGE = "intelligence.story_engine"

_SYSTEM_PROMPT = (
    "You are a scriptwriter and creative director for short vertical videos (Reels, Shorts, TikTok). "
    "Given a topic, return ONLY valid JSON (no markdown fences, no prose) matching this shape:\n"
    '{"hook": str, "mood": str, "scenes": ['
    '{"narration": str, "image_prompt": str, "duration_seconds": number, "mood": str}'
    "]}\n"
    "Rules:\n"
    "- Write 4 to 6 scenes, each duration_seconds between 4 and 8. Scene 1 is a scroll-stopping hook; "
    "the last scene is a clear takeaway or a question that invites comments.\n"
    "- Keep EVERY named person, team, brand, place or product from the topic exactly as written, and stay "
    "on the user's angle. A 'versus', 'vs' or 'better than' topic is a head-to-head comparison: give each "
    "side its own beats, then close with a verdict clearly framed as opinion.\n"
    "- Never invent statistics, dates, records or quotes. Use widely known facts only, or hedge honestly "
    "('many fans argue').\n"
    "- narration is read aloud by a voice: short conversational sentences, no bullet points, no emojis, "
    "no stage directions, no hashtags.\n"
    "- image_prompt describes ONE vertical 9:16 still for that scene: concrete subject, setting, lighting, "
    "camera angle and mood, subject centered. Never depict a real person's face or likeness: show what they "
    "are known for instead (their equipment, vehicle, kit, trophies, workplace, silhouettes, crowds seen from "
    "behind, hands, symbolic scenes). No text, captions, logos or watermarks inside the image. Write "
    "image_prompt in English.\n"
    "- The image generator knows NO names: not people, teams, companies, products, places or events. So every "
    "image_prompt must be self-contained: replace each name with the concrete visual identity it implies "
    "(colours, uniforms or liveries, numbers, materials, shapes, architecture, landscape, era, setting), using "
    "what you genuinely know about the topic. A sports star becomes their sport, kit colours and arena; a "
    "company becomes its product and workplace; a city becomes its landmarks and streets; a historic event "
    "becomes its period clothing, place and objects. Each image_prompt must make sense on its own."
)

# image_prompt stays English in every language, since it's consumed by an
# image generator, not read aloud - only hook/narration need translating.
_LANGUAGE_INSTRUCTIONS = {
    Language.EN: "Write the hook and all narration in English.",
    Language.HI: (
        "Write the hook and all narration entirely in Hindi, using Devanagari "
        "script (not Latin transliteration). Keep every image_prompt in English."
    ),
    Language.HINGLISH: (
        "Write the hook and all narration in natural Hinglish (Hindi-English "
        "code-switched, as commonly spoken in urban India), using Latin script "
        "only - no Devanagari. Keep every image_prompt in English."
    ),
}


def _build_system_prompt(language: Language, style: str = "auto", style_prompt: str | None = None) -> str:
    parts = [_SYSTEM_PROMPT, _LANGUAGE_INSTRUCTIONS[language]]
    tone = styles.tone_for(style, style_prompt)
    if tone:
        parts.append(f"Style of the video: {tone}")
    visual = styles.visual_for(style, style_prompt)
    if visual:
        parts.append(
            "Every image_prompt must describe the scene in this visual style (do not describe it as a photo "
            f"if the style is not photographic): {visual}"
        )
    return "\n".join(parts)


def _build_user_prompt(topic: str) -> str:
    return f"Topic: {topic}\nReturn the JSON now."


def _parse_script(topic: str, raw_text: str) -> Script:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidScriptError(STAGE, f"model did not return valid JSON: {exc}") from exc

    scenes = data.get("scenes", [])
    if not scenes:
        raise InvalidScriptError(STAGE, "model returned zero scenes")

    for i, scene in enumerate(scenes):
        scene["index"] = i

    try:
        return Script(
            topic=topic,
            hook=data["hook"],
            mood=data.get("mood", "neutral"),
            scenes=scenes,
        )
    except KeyError as exc:
        raise InvalidScriptError(STAGE, f"missing required field: {exc}") from exc


def _call_gemini(
    topic: str, language: Language, style: str = "auto", style_prompt: str | None = None, model: str | None = None
) -> Script:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")

    # The key goes in a header, not the URL: httpx echoes the URL (and so the
    # key) into every exception message, which ends up in logs and job errors.
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model or settings.gemini_model}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": _build_user_prompt(topic)}]}],
        "systemInstruction": {"parts": [{"text": _build_system_prompt(language, style, style_prompt)}]},
        "generationConfig": {"responseMimeType": "application/json"},
    }
    with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
        response = client.post(url, json=payload, headers={"x-goog-api-key": settings.gemini_api_key})
        response.raise_for_status()
        body = response.json()

    raw_text = body["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_script(topic, raw_text)


def _call_groq(
    topic: str, language: Language, style: str = "auto", style_prompt: str | None = None, model: str | None = None
) -> Script:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    payload = {
        "model": model or settings.groq_model,
        "messages": [
            {"role": "system", "content": _build_system_prompt(language, style, style_prompt)},
            {"role": "user", "content": _build_user_prompt(topic)},
        ],
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()

    raw_text = body["choices"][0]["message"]["content"]
    return _parse_script(topic, raw_text)


def _call_openrouter(
    topic: str, language: Language, style: str = "auto", style_prompt: str | None = None, model: str | None = None
) -> Script:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY not configured")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    payload = {
        "model": model or settings.openrouter_model,
        "messages": [
            {"role": "system", "content": _build_system_prompt(language, style, style_prompt)},
            {"role": "user", "content": _build_user_prompt(topic)},
        ],
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()

    raw_text = body["choices"][0]["message"]["content"]
    return _parse_script(topic, raw_text)


# Local template fallback: same five narrative beats, hand-translated per
# language so the guaranteed last-resort provider keeps its language promise
# too, not just the real LLM providers.
_TEMPLATE_ANGLES: dict[Language, list[tuple[str, str, str]]] = {
    Language.EN: [
        ("the hook", "Here's something you didn't expect about {topic}.", "a striking establishing shot representing {topic}"),
        ("context", "{topic} matters more than most people realize.", "an informative wide shot related to {topic}"),
        ("key point", "The biggest driver behind {topic} is changing fast.", "a close-up illustrating a key detail of {topic}"),
        ("evidence", "The numbers around {topic} tell their own story.", "a visual metaphor for data or growth tied to {topic}"),
        ("takeaway", "So here's what {topic} means for you.", "a closing shot that ties {topic} together"),
    ],
    Language.HI: [
        ("the hook", "{topic} के बारे में एक ऐसी बात जो शायद आपने पहले नहीं सुनी होगी।", "a striking establishing shot representing {topic}"),
        ("context", "{topic} उतना ही महत्वपूर्ण है जितना ज़्यादातर लोग समझते नहीं।", "an informative wide shot related to {topic}"),
        ("key point", "{topic} के पीछे की सबसे बड़ी वजह तेज़ी से बदल रही है।", "a close-up illustrating a key detail of {topic}"),
        ("evidence", "{topic} से जुड़े आंकड़े खुद अपनी कहानी बताते हैं।", "a visual metaphor for data or growth tied to {topic}"),
        ("takeaway", "तो यह है कि {topic} आपके लिए क्या मायने रखता है।", "a closing shot that ties {topic} together"),
    ],
    Language.HINGLISH: [
        ("the hook", "{topic} ke baare mein ek aisi baat jo shaayad aapne pehle nahi suni hogi.", "a striking establishing shot representing {topic}"),
        ("context", "{topic} utna hi important hai jitna zyada log samajhte nahi.", "an informative wide shot related to {topic}"),
        ("key point", "{topic} ke peeche ki sabse badi wajah tezi se badal rahi hai.", "a close-up illustrating a key detail of {topic}"),
        ("evidence", "{topic} se jude numbers khud apni kahani batate hain.", "a visual metaphor for data or growth tied to {topic}"),
        ("takeaway", "Toh yeh hai ki {topic} aapke liye kya matlab rakhta hai.", "a closing shot that ties {topic} together"),
    ],
}

_TEMPLATE_HOOK: dict[Language, str] = {
    Language.EN: "{topic}. Here's what's really going on.",
    Language.HI: "{topic}। असल में क्या हो रहा है, यह जानिए।",
    Language.HINGLISH: "{topic}. Yahi hai jo asal mein ho raha hai.",
}


def _local_template_script(topic: str, language: Language) -> Script:
    """Deterministic, offline, no-key script generator.

    Last resort in the fallback chain: guarantees the Intelligence stage can
    always produce a usable Script even with zero LLM providers configured,
    so the rest of the pipeline (which needs no API keys at all) stays fully
    runnable while real keys are pending.
    """
    scenes = [
        {
            "narration": narration.format(topic=topic),
            "image_prompt": image_prompt.format(topic=topic),
            "duration_seconds": 4.0,
            "mood": "neutral",
            "index": i,
        }
        for i, (_label, narration, image_prompt) in enumerate(_TEMPLATE_ANGLES[language])
    ]
    return Script(
        topic=topic,
        hook=_TEMPLATE_HOOK[language].format(topic=topic),
        mood="neutral",
        scenes=scenes,
    )


def generate_script(
    topic: str, *, language: Language = Language.EN, style: str = "auto", style_prompt: str | None = None
) -> Script:
    providers = [
        Provider(
            name="gemini",
            call=lambda: try_models(
                lambda m: _call_gemini(topic, language, style, style_prompt, model=m),
                models_to_try(settings.gemini_model, settings.gemini_fallback_models),
            ),
        ),
        Provider(
            name="groq",
            call=lambda: try_models(
                lambda m: _call_groq(topic, language, style, style_prompt, model=m),
                models_to_try(settings.groq_model, settings.groq_fallback_models),
            ),
        ),
        Provider(
            name="openrouter",
            call=lambda: try_models(
                lambda m: _call_openrouter(topic, language, style, style_prompt, model=m),
                models_to_try(settings.openrouter_model, settings.openrouter_fallback_models),
            ),
        ),
        Provider(name="local_template", call=lambda: _local_template_script(topic, language)),
    ]
    return call_with_fallback(providers, stage=STAGE)
