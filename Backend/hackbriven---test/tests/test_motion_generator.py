from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.services import motion_generator


# --- 8scale ---


@patch("backend.services.motion_generator.settings")
@patch("backend.services.motion_generator.httpx.Client")
def test_call_eightscale_happy_path(mock_client_cls, mock_settings, tmp_path: Path):
    mock_settings.eightscale_model = "wan-2.2/14b/image-to-video"
    mock_settings.eightscale_resolution = "480p"
    mock_settings.provider_timeout_seconds = 30.0

    submit_response = MagicMock()
    submit_response.raise_for_status.return_value = None
    submit_response.json.return_value = {"requestId": "req123", "status": "IN_QUEUE"}

    poll_response = MagicMock()
    poll_response.raise_for_status.return_value = None
    poll_response.json.return_value = {
        "requestId": "req123",
        "status": "COMPLETED",
        "output": "https://m.8scale.com/req123/out.mp4",
    }

    api_client = MagicMock()
    api_client.post.return_value = submit_response
    api_client.get.return_value = poll_response

    download_response = MagicMock()
    download_response.raise_for_status.return_value = None
    download_response.content = b"FAKE_VIDEO_BYTES"
    download_client = MagicMock()
    download_client.get.return_value = download_response

    mock_client_cls.return_value.__enter__.side_effect = [api_client, download_client]

    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"fake-image")
    out_path = tmp_path / "clip.mp4"

    result = motion_generator._call_eightscale(image_path, "gentle motion", 5.0, out_path, api_key="fake-key")

    assert result == out_path
    assert out_path.read_bytes() == b"FAKE_VIDEO_BYTES"
    submitted_payload = api_client.post.call_args.kwargs["json"]
    assert submitted_payload["seconds"] == 5
    assert submitted_payload["aspect_ratio"] == "9:16"
    assert submitted_payload["image"].startswith("data:image/png;base64,")
    assert api_client.post.call_args.kwargs["headers"]["Authorization"] == "Bearer fake-key"


def test_call_eightscale_rounds_duration_to_nearest_allowed_value():
    assert min(motion_generator._EIGHTSCALE_ALLOWED_SECONDS, key=lambda s: abs(s - 4.0)) in (3, 5)
    assert min(motion_generator._EIGHTSCALE_ALLOWED_SECONDS, key=lambda s: abs(s - 1.0)) == 3
    assert min(motion_generator._EIGHTSCALE_ALLOWED_SECONDS, key=lambda s: abs(s - 6.0)) == 5


@patch("backend.services.motion_generator.settings")
@patch("backend.services.motion_generator.httpx.Client")
def test_call_eightscale_raises_on_failed_status(mock_client_cls, mock_settings, tmp_path: Path):
    mock_settings.eightscale_model = "wan-2.2/14b/image-to-video"
    mock_settings.eightscale_resolution = "480p"
    mock_settings.provider_timeout_seconds = 30.0

    submit_response = MagicMock()
    submit_response.raise_for_status.return_value = None
    submit_response.json.return_value = {"requestId": "req123"}

    poll_response = MagicMock()
    poll_response.raise_for_status.return_value = None
    poll_response.json.return_value = {"requestId": "req123", "status": "FAILED"}

    client = MagicMock()
    client.post.return_value = submit_response
    client.get.return_value = poll_response
    mock_client_cls.return_value.__enter__.return_value = client

    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"fake-image")

    with pytest.raises(motion_generator.MotionGenerationError, match="FAILED"):
        motion_generator._call_eightscale(image_path, "prompt", 5.0, tmp_path / "out.mp4", api_key="fake-key")


# --- Magic Hour ---


@patch("backend.services.motion_generator.settings")
@patch("backend.services.motion_generator.httpx.Client")
def test_call_magic_hour_happy_path(mock_client_cls, mock_settings, tmp_path: Path):
    mock_settings.magic_hour_resolution = "480p"
    mock_settings.provider_timeout_seconds = 30.0

    upload_response = MagicMock()
    upload_response.raise_for_status.return_value = None
    upload_response.json.return_value = {
        "items": [{"upload_url": "https://upload.example/x", "file_path": "api-assets/x.png"}]
    }
    put_response = MagicMock()
    put_response.raise_for_status.return_value = None

    create_response = MagicMock()
    create_response.raise_for_status.return_value = None
    create_response.json.return_value = {"id": "job123"}

    poll_response = MagicMock()
    poll_response.raise_for_status.return_value = None
    poll_response.json.return_value = {
        "status": "complete",
        "download": {"url": "https://videos.example/job123/output.mp4"},
    }

    api_client = MagicMock()
    api_client.post.side_effect = [upload_response, create_response]
    api_client.put.return_value = put_response
    api_client.get.return_value = poll_response

    download_response = MagicMock()
    download_response.raise_for_status.return_value = None
    download_response.content = b"FAKE_VIDEO_BYTES"

    download_client = MagicMock()
    download_client.get.return_value = download_response

    mock_client_cls.return_value.__enter__.side_effect = [api_client, download_client]

    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"fake-image")
    out_path = tmp_path / "clip.mp4"

    result = motion_generator._call_magic_hour(image_path, "a robot waving", 5.0, out_path, api_key="fake-key")

    assert result == out_path
    assert out_path.read_bytes() == b"FAKE_VIDEO_BYTES"
    assert api_client.post.call_count == 2  # upload-urls, then image-to-video
    assert api_client.post.call_args.kwargs["headers"]["Authorization"] == "Bearer fake-key"


@patch("backend.services.motion_generator.time.sleep")
@patch("backend.services.motion_generator.time.monotonic")
def test_magic_hour_poll_raises_on_error_status(mock_monotonic, mock_sleep):
    mock_monotonic.side_effect = [0.0, 1.0]
    client = MagicMock()
    error_response = MagicMock()
    error_response.raise_for_status.return_value = None
    error_response.json.return_value = {"status": "error", "error": "model timeout"}
    client.get.return_value = error_response

    with pytest.raises(motion_generator.MotionGenerationError, match="model timeout"):
        motion_generator._magic_hour_poll_until_complete(client, "job123", "fake-key")


@patch("backend.services.motion_generator.time.sleep")
@patch("backend.services.motion_generator.time.monotonic")
def test_magic_hour_poll_times_out(mock_monotonic, mock_sleep):
    mock_monotonic.side_effect = [0.0, 0.0, 999999.0]
    client = MagicMock()
    rendering_response = MagicMock()
    rendering_response.raise_for_status.return_value = None
    rendering_response.json.return_value = {"status": "rendering"}
    client.get.return_value = rendering_response

    with pytest.raises(motion_generator.MotionGenerationError, match="did not complete"):
        motion_generator._magic_hour_poll_until_complete(client, "job123", "fake-key")


def test_magic_hour_poll_raises_when_no_download_url():
    client = MagicMock()
    complete_response = MagicMock()
    complete_response.raise_for_status.return_value = None
    complete_response.json.return_value = {"status": "complete", "download": None}
    client.get.return_value = complete_response

    with pytest.raises(motion_generator.MotionGenerationError, match="no download url"):
        motion_generator._magic_hour_poll_until_complete(client, "job123", "fake-key")


# --- generate_motion_clip orchestration (provider chain + key-pool rotation) ---


@patch("backend.services.motion_generator.settings")
@patch("backend.services.motion_generator._call_magic_hour")
@patch("backend.services.motion_generator._call_eightscale")
def test_generate_motion_clip_tries_eightscale_first(mock_eightscale, mock_magic_hour, mock_settings, tmp_path: Path):
    mock_settings.eightscale_key_pool = ["es-key-1"]
    mock_settings.magic_hour_key_pool = ["mh-key-1"]
    out_path = tmp_path / "clip.mp4"
    mock_eightscale.return_value = out_path

    result = motion_generator.generate_motion_clip(tmp_path / "img.png", "prompt", 5.0, out_path)

    assert result == out_path
    mock_eightscale.assert_called_once()
    mock_magic_hour.assert_not_called()


@patch("backend.services.motion_generator.settings")
@patch("backend.services.motion_generator._call_magic_hour")
@patch("backend.services.motion_generator._call_eightscale")
def test_generate_motion_clip_falls_back_to_magic_hour(mock_eightscale, mock_magic_hour, mock_settings, tmp_path: Path):
    mock_settings.eightscale_key_pool = ["es-key-1"]
    mock_settings.magic_hour_key_pool = ["mh-key-1"]
    out_path = tmp_path / "clip.mp4"
    mock_eightscale.side_effect = motion_generator.MotionGenerationError("8scale free generations exhausted")
    mock_magic_hour.return_value = out_path

    result = motion_generator.generate_motion_clip(tmp_path / "img.png", "prompt", 5.0, out_path)

    assert result == out_path
    mock_eightscale.assert_called_once()
    mock_magic_hour.assert_called_once()


@patch("backend.services.motion_generator.settings")
@patch("backend.services.motion_generator._call_eightscale")
def test_generate_motion_clip_rotates_through_eightscale_key_pool(mock_eightscale, mock_settings, tmp_path: Path):
    """Three accounts' keys for the same provider: the first two are
    exhausted/dead, the third succeeds - proves rotation happens *within*
    a provider before ever considering the next provider in the chain."""
    mock_settings.eightscale_key_pool = ["es-key-1", "es-key-2", "es-key-3"]
    mock_settings.magic_hour_key_pool = []
    out_path = tmp_path / "clip.mp4"

    mock_eightscale.side_effect = [
        motion_generator.MotionGenerationError("account 1 quota exhausted"),
        motion_generator.MotionGenerationError("account 2 quota exhausted"),
        out_path,
    ]

    result = motion_generator.generate_motion_clip(tmp_path / "img.png", "prompt", 5.0, out_path)

    assert result == out_path
    assert mock_eightscale.call_count == 3
    used_keys = [call.kwargs["api_key"] for call in mock_eightscale.call_args_list]
    assert used_keys == ["es-key-1", "es-key-2", "es-key-3"]


@patch("backend.services.motion_generator.settings")
@patch("backend.services.motion_generator._call_magic_hour")
@patch("backend.services.motion_generator._call_eightscale")
def test_generate_motion_clip_raises_when_both_providers_fail(mock_eightscale, mock_magic_hour, mock_settings, tmp_path: Path):
    from backend.core.exceptions import AllProvidersFailedError

    mock_settings.eightscale_key_pool = ["es-key-1"]
    mock_settings.magic_hour_key_pool = ["mh-key-1"]
    mock_eightscale.side_effect = motion_generator.MotionGenerationError("8scale down")
    mock_magic_hour.side_effect = motion_generator.MotionGenerationError("magic hour down")

    with pytest.raises(AllProvidersFailedError):
        motion_generator.generate_motion_clip(tmp_path / "img.png", "prompt", 5.0, tmp_path / "out.mp4")


@patch("backend.services.motion_generator.settings")
def test_generate_motion_clip_raises_when_no_keys_configured(mock_settings, tmp_path: Path):
    from backend.core.exceptions import AllProvidersFailedError

    mock_settings.eightscale_key_pool = []
    mock_settings.magic_hour_key_pool = []

    with pytest.raises(AllProvidersFailedError):
        motion_generator.generate_motion_clip(tmp_path / "img.png", "prompt", 5.0, tmp_path / "out.mp4")
