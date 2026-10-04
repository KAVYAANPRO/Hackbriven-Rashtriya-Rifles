from __future__ import annotations

import logging
from pathlib import Path

from backend.config import settings
from backend.core.exceptions import CompositionError
from backend.models.schemas import MotionTier, SceneAssets
from backend.services import motion_generator, upscaler
from backend.utils.ffmpeg_utils import run_ffmpeg

logger = logging.getLogger(__name__)

STAGE = "composition"

_FPS = 30
_CAPTION_GROUP_SIZE = 4
_HIGHLIGHT_COLOR = "&H00FFFF&"  # ASS is BGR: this is yellow (R=FF,G=FF,B=00)
_BASE_COLOR = "&HFFFFFF&"  # white


def _ass_timestamp(seconds: float) -> str:
    total_centis = max(0, round(seconds * 100))
    hours, remainder = divmod(total_centis, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, centis = divmod(remainder, 100)
    return f"{hours:01d}:{minutes:02d}:{secs:02d}.{centis:02d}"


def build_ass_captions(scenes: list[SceneAssets], out_path: Path) -> Path:
    """Render phrase-grouped captions (a few words at a time, like CapCut/
    TikTok-style captions) with the currently-spoken word highlighted in
    yellow, rather than one bare word flashing alone on screen.

    Pure/offline: no ffmpeg call, so this is directly unit-testable.
    """
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {settings.target_width}\n"
        f"PlayResY: {settings.target_height}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
        "Style: Caption,Arial,58,&H00FFFFFF,&H00000000,&H80000000,1,3,1,2,60,60,180\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Text\n"
    )

    lines: list[str] = []
    offset = 0.0
    for scene in sorted(scenes, key=lambda s: s.index):
        words = scene.caption_words
        for group_start in range(0, len(words), _CAPTION_GROUP_SIZE):
            group = words[group_start:group_start + _CAPTION_GROUP_SIZE]
            for highlight_idx, active_word in enumerate(group):
                # word.start_seconds/end_seconds are local to this scene's own
                # audio clip (Whisper transcribes each scene's audio in
                # isolation, starting at 0) - shift by every preceding
                # scene's duration to land at the right time in the final
                # concatenated video.
                start = _ass_timestamp(offset + active_word.start_seconds)
                end = _ass_timestamp(offset + active_word.end_seconds)
                rendered_words = []
                for word_idx, word in enumerate(group):
                    if word_idx == highlight_idx:
                        rendered_words.append(f"{{\\c{_HIGHLIGHT_COLOR}}}{word.word}{{\\c{_BASE_COLOR}}}")
                    else:
                        rendered_words.append(word.word)
                phrase = " ".join(rendered_words)
                lines.append(f"Dialogue: 0,{start},{end},Caption,{{\\b1}}{phrase}{{\\b0}}")
        offset += scene.duration_seconds

    out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out_path


_KEN_BURNS_MAX_ZOOM = 1.15


def _ken_burns_expr(variant: int, total_frames: int) -> tuple[str, str, str]:
    """One of several distinct pan/zoom motions, cycled by scene index so
    consecutive scenes don't all play the identical zoom-in. Centered zoom
    formulas and the zoom-out on(0) reset trick are the standard ffmpeg
    zoompan Ken Burns patterns; `on` is zoompan's built-in output-frame-number
    variable."""
    last_frame = max(total_frames - 1, 1)
    centered_x, centered_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    variants: list[tuple[str, str, str]] = [
        (f"min(zoom+0.0012,{_KEN_BURNS_MAX_ZOOM})", centered_x, centered_y),  # zoom in
        (f"if(eq(on,0),{_KEN_BURNS_MAX_ZOOM},max(1.001,zoom-0.0012))", centered_x, centered_y),  # zoom out
        (str(_KEN_BURNS_MAX_ZOOM), f"(iw-iw/zoom)*on/{last_frame}", centered_y),  # pan left->right
        (str(_KEN_BURNS_MAX_ZOOM), f"(iw-iw/zoom)*(1-on/{last_frame})", centered_y),  # pan right->left
        (str(_KEN_BURNS_MAX_ZOOM), centered_x, f"(ih-ih/zoom)*on/{last_frame}"),  # pan top->bottom
    ]
    return variants[variant % len(variants)]


def _build_scene_clip(image_path: Path, duration_seconds: float, out_path: Path, *, variant: int = 0) -> Path:
    """Ken Burns clip for one scene. Scales to 3x target resolution first
    (not 2x) so the zoompan crop window has more subpixel headroom - at 2x
    the pan/zoom motion visibly stepped/jittered frame to frame, especially
    on the pan variants. Runs at 30fps (not 25) for smoother motion, and
    ends with a light vignette for a less flat, more "produced" look."""
    width, height = settings.target_width, settings.target_height
    total_frames = max(1, round(duration_seconds * _FPS))
    z, x, y = _ken_burns_expr(variant, total_frames)
    zoompan = (
        f"scale={width * 3}:{height * 3}:flags=lanczos,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={total_frames}:s={width}x{height}:fps={_FPS},"
        f"vignette,"
        f"format=yuv420p"
    )
    run_ffmpeg(
        [
            "-loop", "1",
            "-i", str(image_path),
            "-t", str(duration_seconds),
            "-vf", zoompan,
            str(out_path),
        ],
        stage=f"{STAGE}.ken_burns",
    )
    return out_path


def _normalize_clip(raw_path: Path, duration_seconds: float, out_path: Path) -> Path:
    """Conform an externally-generated clip (Magic Hour) to the exact same
    contract every Ken Burns clip already has: target resolution (cropped to
    fill, not stretched), target fps, exact duration, yuv420p. The crossfade
    chain's duration math depends on every clip being precisely this long -
    an unconformed clip would silently desync the whole timeline."""
    width, height = settings.target_width, settings.target_height
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"fps={_FPS},"
        f"format=yuv420p"
    )
    run_ffmpeg(
        [
            "-i", str(raw_path),
            "-t", str(duration_seconds),
            "-vf", vf,
            "-an",
            str(out_path),
        ],
        stage=f"{STAGE}.normalize_motion",
    )
    return out_path


def _build_motion_clip(image_path: Path, prompt: str, duration_seconds: float, out_path: Path) -> Path:
    """Real generative video via Magic Hour, normalized to this pipeline's
    clip contract. Raises on any failure - callers must catch and fall back
    to Ken Burns, since this is a paid/credit-metered external call that can
    fail for reasons having nothing to do with this pipeline (quota, network,
    model timeout)."""
    raw_path = out_path.with_suffix(".raw.mp4")
    motion_generator.generate_motion_clip(image_path, prompt, duration_seconds, raw_path)
    # The motion providers only deliver 480p; run it through the enhancer first when one is available.
    enhanced = upscaler.enhance_clip(raw_path)
    _normalize_clip(enhanced or raw_path, duration_seconds, out_path)
    return out_path


_TRANSITION_DURATION_SECONDS = 0.4
_TRANSITION_STYLES = ["fade", "wiperight", "circleopen", "slideleft", "diagtl"]


def _concat_media(paths: list[Path], out_path: Path, list_file: Path) -> Path:
    list_file.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in paths), encoding="utf-8"
    )
    run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)],
        stage=f"{STAGE}.concat",
    )
    return out_path


def _crossfade_video(clip_paths: list[Path], durations: list[float], out_path: Path) -> Path:
    """Chain xfade transitions between scene clips instead of hard cuts.

    Each non-last clip must already have been rendered TRANSITION_DURATION
    seconds longer than its nominal scene duration (see compose()) so that
    the overlap consumed by the crossfade doesn't shorten the perceived
    on-screen time of any scene - the final combined duration comes out to
    exactly sum(durations), matching the audio/caption timeline untouched.
    This is the standard ffmpeg xfade chaining formula: transition k starts
    at offset = sum(durations[:k+1]) (nominal, unextended) into the
    progressively-merged stream.
    """
    t = _TRANSITION_DURATION_SECONDS
    inputs: list[str] = []
    for p in clip_paths:
        inputs += ["-i", str(p)]

    filter_parts = []
    node = "0:v"
    cumulative = 0.0
    for i in range(1, len(clip_paths)):
        cumulative += durations[i - 1]
        next_node = f"v{i}"
        style = _TRANSITION_STYLES[(i - 1) % len(_TRANSITION_STYLES)]
        filter_parts.append(
            f"[{node}][{i}:v]xfade=transition={style}:duration={t}:offset={cumulative}[{next_node}]"
        )
        node = next_node

    filter_complex = ";".join(filter_parts)
    run_ffmpeg(
        [
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{node}]",
            str(out_path),
        ],
        stage=f"{STAGE}.crossfade",
    )
    return out_path


def _select_motion_scene_positions(scene_count: int, max_count: int) -> set[int]:
    """Which scene positions (0-indexed, in ordered_scenes order) should try
    real generative motion instead of Ken Burns. Opening and closing scenes
    carry the most visual weight, so they're prioritized first when the
    budget is limited; a budget covering every scene (MotionTier.MAX)
    selects all of them."""
    if max_count <= 0 or scene_count == 0:
        return set()
    if max_count >= scene_count:
        return set(range(scene_count))
    priority = [0, scene_count - 1] + list(range(1, scene_count - 1))
    return set(priority[:max_count])


def _motion_budget_for_tier(tier: MotionTier, scene_count: int) -> int:
    """How many scenes may attempt real generative motion, before the
    settings.magic_hour_api_key gate is even checked."""
    if tier == MotionTier.MAX:
        return scene_count  # every scene
    if tier == MotionTier.BALANCED:
        return settings.magic_hour_max_scenes_per_job
    return 0  # BASIC: Ken Burns only, zero credits spent


def compose(
    scenes: list[SceneAssets],
    job_dir: Path,
    *,
    music_path: Path | None = None,
    motion_tier: MotionTier = MotionTier.BALANCED,
) -> Path:
    """Combine per-scene images + audio + captions into one publish-ready MP4.

    Pipeline: per-scene clip (real generative motion for scenes selected by
    motion_tier when MAGIC_HOUR_API_KEY is configured, Ken Burns for the
    rest) -> crossfade video -> concat audio -> burn phrase-grouped captions
    -> loudness-normalise (+ optional music ducking) -> H.264 export.
    """
    if not scenes:
        raise CompositionError(STAGE, "no scenes to compose")

    job_dir.mkdir(parents=True, exist_ok=True)
    ordered_scenes = sorted(scenes, key=lambda s: s.index)
    durations = [s.duration_seconds for s in ordered_scenes]
    has_transitions = len(ordered_scenes) > 1

    has_motion_provider = bool(settings.eightscale_key_pool or settings.magic_hour_key_pool)
    motion_budget = _motion_budget_for_tier(motion_tier, len(ordered_scenes))
    motion_positions = (
        _select_motion_scene_positions(len(ordered_scenes), motion_budget)
        if has_motion_provider
        else set()
    )

    scene_clip_paths: list[Path] = []
    for i, scene in enumerate(ordered_scenes):
        clip_path = job_dir / f"scene_{scene.index:02d}_clip.mp4"
        # Every clip except the last is rendered TRANSITION_DURATION seconds
        # longer than its nominal duration, so the xfade overlap has real
        # extra footage to consume instead of cutting the scene short.
        is_last = i == len(ordered_scenes) - 1
        render_duration = scene.duration_seconds if (is_last or not has_transitions) else scene.duration_seconds + _TRANSITION_DURATION_SECONDS

        made_motion_clip = False
        if i in motion_positions:
            try:
                _build_motion_clip(Path(scene.image_path), scene.image_prompt, render_duration, clip_path)
                made_motion_clip = True
            except Exception as exc:  # noqa: BLE001 - any motion failure falls back to Ken Burns
                logger.warning("scene=%s motion generation failed, falling back to Ken Burns: %s", scene.index, exc)

        if not made_motion_clip:
            _build_scene_clip(Path(scene.image_path), render_duration, clip_path, variant=scene.index)
        scene_clip_paths.append(clip_path)

    silent_video = job_dir / "silent.mp4"
    if has_transitions:
        _crossfade_video(scene_clip_paths, durations, silent_video)
    else:
        _concat_media(scene_clip_paths, silent_video, job_dir / "video_concat.txt")

    audio_paths = [Path(s.audio_path) for s in ordered_scenes]
    narration_audio = job_dir / "narration.wav"
    _concat_media(audio_paths, narration_audio, job_dir / "audio_concat.txt")

    captions_path = build_ass_captions(scenes, job_dir / "captions.ass")

    with_captions = job_dir / "with_captions.mp4"
    run_ffmpeg(
        [
            "-i", str(silent_video),
            "-vf", f"subtitles={captions_path.as_posix()}",
            "-an",
            str(with_captions),
        ],
        stage=f"{STAGE}.captions",
    )

    final_path = job_dir / "final.mp4"
    audio_filter = "loudnorm=I=-16:TP=-1.5:LRA=11"
    if music_path is not None:
        run_ffmpeg(
            [
                "-i", str(with_captions),
                "-i", str(narration_audio),
                "-i", str(music_path),
                "-filter_complex",
                f"[2:a]volume=0.25[music];"
                f"[1:a][music]sidechaincompress=threshold=0.05:ratio=8[ducked];"
                f"[1:a][ducked]amix=inputs=2:duration=first,{audio_filter}[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-c:a", "aac",
                str(final_path),
            ],
            stage=f"{STAGE}.mix_duck",
        )
    else:
        run_ffmpeg(
            [
                "-i", str(with_captions),
                "-i", str(narration_audio),
                "-filter:a", audio_filter,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264",
                "-c:a", "aac",
                str(final_path),
            ],
            stage=f"{STAGE}.mix",
        )

    return final_path
