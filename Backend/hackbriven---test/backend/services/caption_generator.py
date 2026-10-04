from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import httpx
import numpy as np

from backend.config import settings
from backend.models.schemas import CaptionWord, Language
from backend.services.model_router import Provider, call_with_fallback
from backend.utils.ffmpeg_utils import ffmpeg_path

logger = logging.getLogger(__name__)

STAGE = "generation.captions"

_WHISPER_SAMPLE_RATE = 16000

_model_cache: dict[str, object] = {}


# --- Groq-hosted Whisper (tried first: cloud GPU, faster and more accurate
# than the local CPU model below, free tier, no new key - reuses GROQ_API_KEY) ---


_WHISPER_LANGUAGE_CODE = {
    # Hindi audio is Devanagari-script hi-IN speech - giving Whisper an
    # explicit language hint noticeably improves accuracy over auto-detect.
    # English and Hinglish audio are both Latin-script, English-family
    # voices (en-US/en-IN), so "en" is correct for both and also skips the
    # auto-detect pass (a small speed win, not just accuracy).
    Language.EN: "en",
    Language.HI: "hi",
    Language.HINGLISH: "en",
}


def _call_groq_whisper(audio_path: Path, language: Language = Language.EN) -> list[CaptionWord]:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    with open(audio_path, "rb") as f:
        files = {"file": (audio_path.name, f, "audio/mpeg")}
        data = {
            "model": settings.groq_whisper_model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "word",
            "language": _WHISPER_LANGUAGE_CODE[language],
        }
        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        with httpx.Client(timeout=settings.provider_timeout_seconds) as client:
            response = client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                files=files, data=data, headers=headers,
            )
    response.raise_for_status()
    body = response.json()

    words: list[CaptionWord] = []
    for word in body.get("words") or []:
        token = str(word.get("word", "")).strip()
        if not token:
            continue
        words.append(
            CaptionWord(word=token, start_seconds=float(word["start"]), end_seconds=float(word["end"]))
        )

    if not words:
        raise RuntimeError("groq whisper produced no word-level timestamps")
    return words


# --- Local faster-whisper (fallback: no network dependency, keyless) ---


def _load_model():
    name = settings.whisper_model
    if name not in _model_cache:
        from faster_whisper import WhisperModel

        _model_cache[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _model_cache[name]


def _decode_audio(audio_path: Path) -> np.ndarray:
    """Decode to 16kHz mono float32 PCM via the ffmpeg binary directly,
    bypassing faster-whisper's own av-based decoder - the installed `av`
    wheel on this Python/OS combo is ABI-incompatible with faster-whisper's
    expected API (no prebuilt wheel for an older, compatible av exists for
    this Python version, and building from source needs ffmpeg dev headers
    we don't have). Passing a numpy array to transcribe() skips av entirely.
    """
    cmd = [
        ffmpeg_path(),
        "-i", str(audio_path),
        "-f", "f32le",
        "-ac", "1",
        "-ar", str(_WHISPER_SAMPLE_RATE),
        "-loglevel", "error",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio decode failed: {result.stderr.decode(errors='replace').strip()}")

    return np.frombuffer(result.stdout, dtype=np.float32)


def _call_local_whisper(audio_path: Path, language: Language = Language.EN) -> list[CaptionWord]:
    model = _load_model()
    audio = _decode_audio(audio_path)
    segments, _info = model.transcribe(audio, word_timestamps=True, language=_WHISPER_LANGUAGE_CODE[language])

    words: list[CaptionWord] = []
    for segment in segments:
        for word in segment.words or []:
            token = str(word.word).strip()
            if not token:
                continue
            words.append(
                CaptionWord(
                    word=token,
                    start_seconds=float(word.start),
                    end_seconds=float(word.end),
                )
            )

    if not words:
        raise RuntimeError("local whisper produced no word-level timestamps")
    return words


def transcribe(audio_path: Path, *, language: Language = Language.EN) -> list[CaptionWord]:
    providers = [
        Provider(name="groq_whisper", call=lambda: _call_groq_whisper(audio_path, language)),
        Provider(name="local_whisper", call=lambda: _call_local_whisper(audio_path, language)),
    ]
    return call_with_fallback(providers, stage=STAGE)
