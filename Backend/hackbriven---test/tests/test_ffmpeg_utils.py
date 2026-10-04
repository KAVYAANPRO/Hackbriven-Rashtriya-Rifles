from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.exceptions import PipelineError
from backend.utils import ffmpeg_utils
from backend.utils.ffmpeg_utils import FfmpegNotAvailableError, _resolve_binaries


@pytest.fixture(autouse=True)
def _reset_resolution_cache():
    ffmpeg_utils._resolved_paths = None
    yield
    ffmpeg_utils._resolved_paths = None


@patch("backend.utils.ffmpeg_utils.shutil.which")
def test_resolve_binaries_prefers_path(mock_which):
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"

    ffmpeg_path, ffprobe_path = _resolve_binaries()

    assert ffmpeg_path == "/usr/bin/ffmpeg"
    assert ffprobe_path == "/usr/bin/ffprobe"


@patch("backend.utils.ffmpeg_utils.shutil.which", return_value=None)
@patch("static_ffmpeg.run.get_or_fetch_platform_executables_else_raise")
def test_resolve_binaries_falls_back_to_static_ffmpeg(mock_fetch, mock_which):
    mock_fetch.return_value = ("/cache/ffmpeg", "/cache/ffprobe")

    ffmpeg_path, ffprobe_path = _resolve_binaries()

    assert ffmpeg_path == "/cache/ffmpeg"
    assert ffprobe_path == "/cache/ffprobe"
    mock_fetch.assert_called_once()


@patch("backend.utils.ffmpeg_utils.shutil.which", return_value=None)
@patch("static_ffmpeg.run.get_or_fetch_platform_executables_else_raise")
def test_resolve_binaries_raises_when_both_fail(mock_fetch, mock_which):
    mock_fetch.side_effect = RuntimeError("no network")

    with pytest.raises(FfmpegNotAvailableError):
        _resolve_binaries()


@patch("backend.utils.ffmpeg_utils.shutil.which")
def test_resolve_binaries_caches_result(mock_which):
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"

    _resolve_binaries()
    _resolve_binaries()

    assert mock_which.call_count == 2  # one call per binary, only on the first resolve


@patch("backend.utils.ffmpeg_utils.probe")
def test_get_duration_seconds_returns_float(mock_probe, tmp_path):
    mock_probe.return_value = {"format": {"duration": "12.34"}}

    result = ffmpeg_utils.get_duration_seconds(tmp_path / "clip.mp4")

    assert result == 12.34


@patch("backend.utils.ffmpeg_utils.probe")
def test_get_duration_seconds_raises_when_missing(mock_probe, tmp_path):
    mock_probe.return_value = {"format": {}}

    with pytest.raises(RuntimeError, match="no duration"):
        ffmpeg_utils.get_duration_seconds(tmp_path / "clip.mp4")
