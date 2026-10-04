from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core.exceptions import AllProvidersFailedError
from backend.models.schemas import Language
from backend.services import voice_generator


def test_synthesize_uses_edge_tts_when_it_succeeds(tmp_path: Path) -> None:
    out_path = tmp_path / "scene.mp3"

    with patch.object(voice_generator, "_call_edge_tts", return_value=out_path) as mock_edge, \
         patch.object(voice_generator, "_call_gtts") as mock_gtts:
        result = voice_generator.synthesize("hello world", out_path, language=Language.EN)

    assert result == out_path
    mock_edge.assert_called_once()
    mock_gtts.assert_not_called()


def test_synthesize_falls_back_to_gtts_when_edge_tts_fails(tmp_path: Path) -> None:
    out_path = tmp_path / "scene.mp3"

    with patch.object(voice_generator, "_call_edge_tts", side_effect=RuntimeError("edge-tts down")), \
         patch.object(voice_generator, "_call_gtts", return_value=out_path) as mock_gtts:
        result = voice_generator.synthesize("hello world", out_path, language=Language.EN)

    assert result == out_path
    mock_gtts.assert_called_once()


def test_synthesize_raises_when_both_providers_fail(tmp_path: Path) -> None:
    out_path = tmp_path / "scene.mp3"

    with patch.object(voice_generator, "_call_edge_tts", side_effect=RuntimeError("edge-tts down")), \
         patch.object(voice_generator, "_call_gtts", side_effect=RuntimeError("gtts down")):
        with pytest.raises(AllProvidersFailedError):
            voice_generator.synthesize("hello world", out_path, language=Language.EN)


def test_gtts_lang_mapping_covers_all_languages() -> None:
    assert voice_generator._GTTS_LANG_BY_LANGUAGE[Language.EN] == "en"
    assert voice_generator._GTTS_LANG_BY_LANGUAGE[Language.HI] == "hi"
    assert voice_generator._GTTS_LANG_BY_LANGUAGE[Language.HINGLISH] == "en"


def test_call_gtts_raises_on_empty_output(tmp_path: Path) -> None:
    out_path = tmp_path / "empty.mp3"

    class _FakeGTTS:
        def __init__(self, text: str, lang: str) -> None:
            pass

        def save(self, path: str) -> None:
            Path(path).touch()  # zero-byte file, simulates a broken/empty save

    with patch("gtts.gTTS", _FakeGTTS):
        with pytest.raises(RuntimeError):
            voice_generator._call_gtts("hello", out_path, Language.EN)
