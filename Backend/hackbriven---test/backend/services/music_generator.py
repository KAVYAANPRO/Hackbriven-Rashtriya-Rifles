from __future__ import annotations

from pathlib import Path

from backend.utils.ffmpeg_utils import run_ffmpeg

STAGE = "generation.music"

# No royalty-free music library is wired in (downloading third-party audio
# files isn't something to do without the user picking a specific, verified
# source - see DEPLOYMENT.md §13). Instead this synthesizes a simple ambient
# pad directly with ffmpeg's own sine-wave generator: zero downloads, zero
# licensing questions, and it's exactly what a quiet background bed under
# narration needs to be - subtle, not a lead instrument. video_composer's
# existing sidechain-ducking already attenuates this further under speech.
_CHORDS = {
    "upbeat": [261.63, 329.63, 392.00],  # C major triad
    "calm": [220.00, 261.63, 329.63],  # A minor triad
}

_UPBEAT_KEYWORDS = ("upbeat", "energetic", "exciting", "hopeful", "fun", "playful")


def _chord_for_mood(mood: str) -> list[float]:
    mood_lower = (mood or "").lower()
    if any(keyword in mood_lower for keyword in _UPBEAT_KEYWORDS):
        return _CHORDS["upbeat"]
    return _CHORDS["calm"]


def generate_ambient_bed(mood: str, duration_seconds: float, out_path: Path) -> Path:
    """Synthesize a quiet ambient pad of the given duration and mood,
    suitable as video_composer.compose()'s music_path."""
    frequencies = _chord_for_mood(mood)
    duration = max(duration_seconds, 1.0)
    fade_duration = min(2.0, duration / 4)
    fade_out_start = max(duration - fade_duration, 0.0)

    inputs: list[str] = []
    for freq in frequencies:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}"]

    mix_inputs = "".join(f"[{i}:a]" for i in range(len(frequencies)))
    filter_complex = (
        f"{mix_inputs}amix=inputs={len(frequencies)}:duration=longest,"
        f"lowpass=f=2000,"
        f"tremolo=f=0.2:d=0.3,"
        f"volume=0.5,"
        f"afade=t=in:st=0:d={fade_duration},"
        f"afade=t=out:st={fade_out_start}:d={fade_duration}[aout]"
    )

    run_ffmpeg(
        [
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-ar", "44100",
            "-ac", "2",
            str(out_path),
        ],
        stage=STAGE,
    )
    return out_path
