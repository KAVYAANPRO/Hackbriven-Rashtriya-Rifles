from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from backend.services import quality_gate


def _fake_probe(width=1080, height=1920, duration="12.4", has_audio=True):
    streams = [{"codec_type": "video", "width": width, "height": height}]
    if has_audio:
        streams.append({"codec_type": "audio", "channels": 2})
    return {"streams": streams, "format": {"duration": duration}}


@patch("backend.services.quality_gate.settings")
@patch("backend.services.quality_gate.probe")
def test_check_passes_valid_video(mock_probe, mock_settings, tmp_path: Path):
    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")
    mock_probe.return_value = _fake_probe()

    report = quality_gate.check(video, expected_duration_seconds=12.5)

    assert report.passed is True
    assert report.reasons == []


@patch("backend.services.quality_gate.settings")
@patch("backend.services.quality_gate.probe")
def test_check_fails_wrong_resolution(mock_probe, mock_settings, tmp_path: Path):
    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")
    mock_probe.return_value = _fake_probe(width=720, height=1280)

    report = quality_gate.check(video, expected_duration_seconds=12.5)

    assert report.passed is False
    assert any("resolution" in r for r in report.reasons)


@patch("backend.services.quality_gate.settings")
@patch("backend.services.quality_gate.probe")
def test_check_fails_missing_audio(mock_probe, mock_settings, tmp_path: Path):
    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")
    mock_probe.return_value = _fake_probe(has_audio=False)

    report = quality_gate.check(video, expected_duration_seconds=12.5)

    assert report.passed is False
    assert any("audio" in r for r in report.reasons)


def test_check_fails_on_missing_file(tmp_path: Path):
    report = quality_gate.check(tmp_path / "missing.mp4", expected_duration_seconds=10.0)
    assert report.passed is False
    assert "output file missing or empty" in report.reasons
