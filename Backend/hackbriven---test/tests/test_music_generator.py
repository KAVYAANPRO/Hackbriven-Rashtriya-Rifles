from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from backend.services import music_generator


def test_chord_for_mood_picks_upbeat_on_keyword() -> None:
    assert music_generator._chord_for_mood("Upbeat and exciting") == music_generator._CHORDS["upbeat"]


def test_chord_for_mood_defaults_to_calm() -> None:
    assert music_generator._chord_for_mood("serious") == music_generator._CHORDS["calm"]
    assert music_generator._chord_for_mood("") == music_generator._CHORDS["calm"]


def test_generate_ambient_bed_invokes_ffmpeg_with_three_sine_inputs(tmp_path: Path) -> None:
    out_path = tmp_path / "music.wav"

    with patch.object(music_generator, "run_ffmpeg") as mock_run:
        result = music_generator.generate_ambient_bed("upbeat", 10.0, out_path)

    assert result == out_path
    args = mock_run.call_args[0][0]
    assert args.count("lavfi") == 3  # one sine source per chord note
    assert str(out_path) in args


def test_generate_ambient_bed_clamps_short_durations(tmp_path: Path) -> None:
    out_path = tmp_path / "music.wav"

    with patch.object(music_generator, "run_ffmpeg") as mock_run:
        music_generator.generate_ambient_bed("calm", 0.1, out_path)

    filter_complex = mock_run.call_args[0][0][mock_run.call_args[0][0].index("-filter_complex") + 1]
    assert "duration=longest" in filter_complex
