from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.core.exceptions import InvalidScriptError
from backend.services import story_engine

VALID_JSON = json.dumps(
    {
        "hook": "EVs are taking over.",
        "mood": "upbeat",
        "scenes": [
            {"narration": "Cheaper to run.", "image_prompt": "ev charger", "duration_seconds": 4, "mood": "upbeat"},
            {"narration": "Better for the planet.", "image_prompt": "green forest and ev", "duration_seconds": 4, "mood": "hopeful"},
        ],
    }
)


def _mock_gemini_response(text: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    }
    return response


def _mock_groq_response(text: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"choices": [{"message": {"content": text}}]}
    return response


_mock_openrouter_response = _mock_groq_response  # identical OpenAI-style shape


@patch("backend.services.story_engine.settings")
@patch("backend.services.story_engine.httpx.Client")
def test_generate_script_uses_gemini_when_available(mock_client_cls, mock_settings):
    mock_settings.gemini_api_key = "fake-key"
    mock_settings.groq_api_key = "fake-key"
    mock_settings.gemini_model = "gemini-1.5-flash"
    mock_settings.provider_timeout_seconds = 5.0

    client = MagicMock()
    client.post.return_value = _mock_gemini_response(VALID_JSON)
    mock_client_cls.return_value.__enter__.return_value = client

    script = story_engine.generate_script("Why EVs are popular")

    assert script.hook == "EVs are taking over."
    assert len(script.scenes) == 2
    assert script.scenes[0].index == 0


@patch("backend.services.story_engine.settings")
@patch("backend.services.story_engine.httpx.Client")
def test_generate_script_falls_back_to_groq_on_gemini_failure(mock_client_cls, mock_settings):
    mock_settings.gemini_api_key = "fake-key"
    mock_settings.groq_api_key = "fake-key"
    mock_settings.gemini_model = "gemini-1.5-flash"
    mock_settings.groq_model = "llama-3.1-70b-versatile"
    mock_settings.provider_timeout_seconds = 5.0

    client = MagicMock()

    def post_side_effect(url, **kwargs):
        if "generativelanguage" in url:
            raise RuntimeError("gemini rate limited")
        return _mock_groq_response(VALID_JSON)

    client.post.side_effect = post_side_effect
    mock_client_cls.return_value.__enter__.return_value = client

    script = story_engine.generate_script("Why EVs are popular")

    assert script.hook == "EVs are taking over."
    assert client.post.call_count == 2


@patch("backend.services.story_engine.settings")
@patch("backend.services.story_engine.httpx.Client")
def test_generate_script_falls_back_to_openrouter_when_gemini_and_groq_fail(mock_client_cls, mock_settings):
    mock_settings.gemini_api_key = ""
    mock_settings.groq_api_key = ""
    mock_settings.openrouter_api_key = "fake-key"
    mock_settings.openrouter_model = "nvidia/nemotron-3-super-120b-a12b:free"
    mock_settings.provider_timeout_seconds = 5.0

    client = MagicMock()
    client.post.return_value = _mock_openrouter_response(VALID_JSON)
    mock_client_cls.return_value.__enter__.return_value = client

    script = story_engine.generate_script("Why EVs are popular")

    assert script.hook == "EVs are taking over."
    client.post.assert_called_once()
    assert "openrouter.ai" in client.post.call_args[0][0]


@patch("backend.services.story_engine.settings")
def test_generate_script_falls_back_to_local_template_with_no_keys(mock_settings):
    mock_settings.gemini_api_key = ""
    mock_settings.groq_api_key = ""
    mock_settings.openrouter_api_key = ""

    script = story_engine.generate_script("Why EVs are popular")

    assert script.topic == "Why EVs are popular"
    assert len(script.scenes) == 5
    assert all(s.narration for s in script.scenes)


def test_local_template_script_is_deterministic():
    from backend.models.schemas import Language

    first = story_engine._local_template_script("Why EVs are popular", Language.EN)
    second = story_engine._local_template_script("Why EVs are popular", Language.EN)
    assert first == second


def test_local_template_script_hindi():
    from backend.models.schemas import Language

    script = story_engine._local_template_script("Why EVs are popular", Language.HI)
    assert "Why EVs are popular" in script.hook  # topic substituted, rest is Devanagari
    assert any(ord(c) > 0x0900 for c in script.hook)  # contains Devanagari characters
    assert len(script.scenes) == 5


def test_local_template_script_hinglish():
    from backend.models.schemas import Language

    script = story_engine._local_template_script("Why EVs are popular", Language.HINGLISH)
    assert "Why EVs are popular" in script.hook
    assert "asal mein" in script.hook.lower()
    assert len(script.scenes) == 5


def test_parse_script_rejects_invalid_json():
    with pytest.raises(InvalidScriptError):
        story_engine._parse_script("topic", "not json at all")


def test_parse_script_rejects_zero_scenes():
    with pytest.raises(InvalidScriptError):
        story_engine._parse_script("topic", json.dumps({"hook": "h", "scenes": []}))
