from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backend.config import settings
from backend.models.schemas import Language
from backend.services.model_router import Provider, call_with_fallback

logger = logging.getLogger(__name__)

STAGE = "generation.voice"

_VOICE_BY_LANGUAGE = {
    Language.EN: lambda: settings.edge_tts_voice,
    Language.HI: lambda: settings.edge_tts_voice_hi,
    Language.HINGLISH: lambda: settings.edge_tts_voice_hinglish,
}


def _voice_for_language(language: Language) -> str:
    return _VOICE_BY_LANGUAGE[language]()


async def _synthesize_async(text: str, out_path: Path, voice: str) -> Path:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("edge-tts produced an empty audio file")
    return out_path


def _call_edge_tts(text: str, out_path: Path, language: Language) -> Path:
    return asyncio.run(_synthesize_async(text, out_path, _voice_for_language(language)))


# gTTS (Google Translate's TTS endpoint) needs no API key and has no quota
# we've hit in testing - it's the second link in this stage's fallback chain
# so a single edge-tts outage (Microsoft's service, rate limits, network
# blip) doesn't take down narration entirely during a live demo. Hinglish has
# no dedicated gTTS voice, so it uses the same "en" voice reading Latin-script
# text that edge-tts's en-IN voice does for the same reason.
_GTTS_LANG_BY_LANGUAGE = {
    Language.EN: "en",
    Language.HI: "hi",
    Language.HINGLISH: "en",
}


def _call_gtts(text: str, out_path: Path, language: Language) -> Path:
    from gtts import gTTS

    tts = gTTS(text=text, lang=_GTTS_LANG_BY_LANGUAGE[language])
    tts.save(str(out_path))
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("gTTS produced an empty audio file")
    return out_path


def synthesize(text: str, out_path: Path, *, language: Language = Language.EN) -> Path:
    providers = [
        Provider(name="edge-tts", call=lambda: _call_edge_tts(text, out_path, language)),
        Provider(name="gtts", call=lambda: _call_gtts(text, out_path, language)),
    ]
    return call_with_fallback(providers, stage=STAGE)
