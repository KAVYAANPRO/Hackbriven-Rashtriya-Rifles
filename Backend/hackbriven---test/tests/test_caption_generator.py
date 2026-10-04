from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.core.exceptions import AllProvidersFailedError
from backend.services import caption_generator


def _fake_word(word: str, start: float, end: float) -> SimpleNamespace:
    return SimpleNamespace(word=word, start=start, end=end)


def _fake_segment(words: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(words=words)


# --- Groq Whisper (primary) ---


@patch("backend.services.caption_generator.settings")
@patch("backend.services.caption_generator.httpx.Client")
def test_call_groq_whisper_returns_word_level_captions(mock_client_cls, mock_settings, tmp_path: Path):
    mock_settings.groq_api_key = "fake-key"
    mock_settings.groq_key_pool = ["fake-key"]
    mock_settings.groq_whisper_model = "whisper-large-v3-turbo"
    mock_settings.provider_timeout_seconds = 30.0

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.4},
            {"word": "world", "start": 0.4, "end": 0.9},
        ]
    }
    client = MagicMock()
    client.post.return_value = response
    mock_client_cls.return_value.__enter__.return_value = client

    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"fake-audio")

    words = caption_generator._call_groq_whisper(audio_path)

    assert [w.word for w in words] == ["hello", "world"]
    assert words[0].start_seconds == 0.0
    assert words[1].end_seconds == 0.9


@patch("backend.services.caption_generator.settings")
def test_call_groq_whisper_raises_without_key(mock_settings, tmp_path: Path):
    mock_settings.groq_api_key = ""
    mock_settings.groq_key_pool = []

    with pytest.raises(RuntimeError, match="not configured"):
        caption_generator._call_groq_whisper(tmp_path / "audio.mp3")


@patch("backend.services.caption_generator.settings")
@patch("backend.services.caption_generator.httpx.Client")
def test_call_groq_whisper_raises_when_no_words(mock_client_cls, mock_settings, tmp_path: Path):
    mock_settings.groq_api_key = "fake-key"
    mock_settings.groq_key_pool = ["fake-key"]
    mock_settings.groq_whisper_model = "whisper-large-v3-turbo"
    mock_settings.provider_timeout_seconds = 30.0

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"words": []}
    client = MagicMock()
    client.post.return_value = response
    mock_client_cls.return_value.__enter__.return_value = client

    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"fake-audio")

    with pytest.raises(RuntimeError, match="no word-level timestamps"):
        caption_generator._call_groq_whisper(audio_path)


# --- local faster-whisper (fallback) ---


@patch("backend.services.caption_generator._decode_audio")
@patch("backend.services.caption_generator._load_model")
def test_call_local_whisper_returns_word_level_captions(mock_load_model, mock_decode, tmp_path: Path):
    mock_decode.return_value = np.zeros(16000, dtype=np.float32)
    model = MagicMock()
    model.transcribe.return_value = (
        [_fake_segment([_fake_word("hello", 0.0, 0.4), _fake_word("world", 0.4, 0.9)])],
        object(),
    )
    mock_load_model.return_value = model

    words = caption_generator._call_local_whisper(tmp_path / "audio.mp3")

    assert [w.word for w in words] == ["hello", "world"]
    assert words[0].start_seconds == 0.0
    assert words[1].end_seconds == 0.9


@patch("backend.services.caption_generator._decode_audio")
@patch("backend.services.caption_generator._load_model")
def test_call_local_whisper_skips_blank_words(mock_load_model, mock_decode, tmp_path: Path):
    mock_decode.return_value = np.zeros(16000, dtype=np.float32)
    model = MagicMock()
    model.transcribe.return_value = (
        [_fake_segment([_fake_word("  ", 0.0, 0.1), _fake_word("hi", 0.1, 0.3)])],
        object(),
    )
    mock_load_model.return_value = model

    words = caption_generator._call_local_whisper(tmp_path / "audio.mp3")

    assert [w.word for w in words] == ["hi"]


@patch("backend.services.caption_generator._decode_audio")
@patch("backend.services.caption_generator._load_model")
def test_call_local_whisper_raises_when_no_words_produced(mock_load_model, mock_decode, tmp_path: Path):
    mock_decode.return_value = np.zeros(16000, dtype=np.float32)
    model = MagicMock()
    model.transcribe.return_value = ([_fake_segment([])], object())
    mock_load_model.return_value = model

    with pytest.raises(RuntimeError, match="no word-level timestamps"):
        caption_generator._call_local_whisper(tmp_path / "audio.mp3")


@patch("backend.services.caption_generator.subprocess.run")
@patch("backend.services.caption_generator.ffmpeg_path", return_value="/fake/ffmpeg")
def test_decode_audio_invokes_ffmpeg_and_parses_pcm(mock_ffmpeg_path, mock_run, tmp_path: Path):
    fake_samples = np.array([0.1, -0.2, 0.3], dtype=np.float32)
    mock_run.return_value = MagicMock(returncode=0, stdout=fake_samples.tobytes())

    result = caption_generator._decode_audio(tmp_path / "audio.mp3")

    np.testing.assert_allclose(result, fake_samples)
    args = mock_run.call_args[0][0]
    assert args[0] == "/fake/ffmpeg"
    assert "-ar" in args and "16000" in args


@patch("backend.services.caption_generator.subprocess.run")
@patch("backend.services.caption_generator.ffmpeg_path", return_value="/fake/ffmpeg")
def test_decode_audio_raises_on_ffmpeg_failure(mock_ffmpeg_path, mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(returncode=1, stderr=b"boom")

    with pytest.raises(RuntimeError, match="ffmpeg audio decode failed"):
        caption_generator._decode_audio(tmp_path / "audio.mp3")


# --- transcribe() orchestration (fallback chain) ---


@patch("backend.services.caption_generator._call_local_whisper")
@patch("backend.services.caption_generator._call_groq_whisper")
def test_transcribe_tries_groq_first(mock_groq, mock_local, tmp_path: Path):
    from backend.models.schemas import CaptionWord

    mock_groq.return_value = [CaptionWord(word="hi", start_seconds=0.0, end_seconds=0.3)]

    words = caption_generator.transcribe(tmp_path / "audio.mp3")

    assert [w.word for w in words] == ["hi"]
    mock_groq.assert_called_once()
    mock_local.assert_not_called()


@patch("backend.services.caption_generator._call_local_whisper")
@patch("backend.services.caption_generator._call_groq_whisper")
def test_transcribe_falls_back_to_local_whisper(mock_groq, mock_local, tmp_path: Path):
    from backend.models.schemas import CaptionWord

    mock_groq.side_effect = RuntimeError("groq rate limited")
    mock_local.return_value = [CaptionWord(word="hi", start_seconds=0.0, end_seconds=0.3)]

    words = caption_generator.transcribe(tmp_path / "audio.mp3")

    assert [w.word for w in words] == ["hi"]
    mock_groq.assert_called_once()
    mock_local.assert_called_once()


@patch("backend.services.caption_generator._call_local_whisper")
@patch("backend.services.caption_generator._call_groq_whisper")
def test_transcribe_raises_when_both_fail(mock_groq, mock_local, tmp_path: Path):
    mock_groq.side_effect = RuntimeError("groq down")
    mock_local.side_effect = RuntimeError("local down")

    with pytest.raises(AllProvidersFailedError):
        caption_generator.transcribe(tmp_path / "audio.mp3")
