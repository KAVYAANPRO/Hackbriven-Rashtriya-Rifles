from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.models.schemas import SceneAssets
from backend.services import video_composer


def test_build_ass_captions_contains_every_word(sample_scene_assets: list[SceneAssets], tmp_path: Path):
    out_path = tmp_path / "captions.ass"
    video_composer.build_ass_captions(sample_scene_assets, out_path)

    content = out_path.read_text(encoding="utf-8")
    assert "hello" in content
    assert "world" in content
    assert "[Events]" in content
    assert content.count("Dialogue:") == 4  # 2 scenes x 2 words


def test_ass_timestamp_formats_correctly():
    assert video_composer._ass_timestamp(0.0) == "0:00:00.00"
    assert video_composer._ass_timestamp(65.5) == "0:01:05.50"


def test_build_ass_captions_offsets_by_preceding_scene_durations(sample_scene_assets: list[SceneAssets], tmp_path: Path):
    # Whisper timestamps are local to each scene's own audio clip (start
    # near 0) - in the final concatenated video, scene 1's captions must
    # be shifted later by scene 0's full duration, or they land at the
    # wrong moment (confirmed live: every scene after the first was
    # restarting its captions at 0:00:00.00).
    out_path = tmp_path / "captions.ass"
    video_composer.build_ass_captions(sample_scene_assets, out_path)
    content = out_path.read_text(encoding="utf-8")

    scene0_duration = sample_scene_assets[0].duration_seconds
    scene1_word = sample_scene_assets[1].caption_words[0]
    expected_start = video_composer._ass_timestamp(scene0_duration + scene1_word.start_seconds)

    lines = [line for line in content.splitlines() if "Dialogue:" in line]
    # scene 0 contributes the first 2 lines (2 caption words), so scene 1's
    # first word is line index 2 - both scenes reuse the same word text
    # ("hello"/"world") in this fixture, so matching by text would find
    # scene 0's line instead.
    scene1_first_line = lines[len(sample_scene_assets[0].caption_words)]
    assert scene1_first_line.startswith(f"Dialogue: 0,{expected_start}")
    assert scene1_word.word in scene1_first_line


def test_build_ass_captions_sorts_out_of_order_scenes(sample_scene_assets: list[SceneAssets], tmp_path: Path):
    reversed_scenes = list(reversed(sample_scene_assets))
    out_path = tmp_path / "captions.ass"
    video_composer.build_ass_captions(reversed_scenes, out_path)
    content = out_path.read_text(encoding="utf-8")

    # Both scenes share the same word text ("hello"/"world") in this
    # fixture, so only the timestamp (not the word) distinguishes which
    # scene's line landed first - regardless of input order, scene 0 (the
    # lower index) must always be processed first, at offset 0.
    lines = [line for line in content.splitlines() if "Dialogue:" in line]
    expected_first_start = video_composer._ass_timestamp(
        sample_scene_assets[0].caption_words[0].start_seconds
    )
    assert lines[0].startswith(f"Dialogue: 0,{expected_first_start}")


def test_ken_burns_expr_varies_by_scene_index():
    # The original bug report: every scene played the identical zoom-in,
    # which read as flat/mechanical. Consecutive scene indices must now
    # produce visibly different z/x/y expressions.
    variants = [video_composer._ken_burns_expr(i, total_frames=100) for i in range(5)]
    assert len(set(variants)) == 5  # all 5 built-in variants are distinct


def test_ken_burns_expr_cycles_after_running_out_of_variants():
    first = video_composer._ken_burns_expr(0, total_frames=100)
    wrapped = video_composer._ken_burns_expr(5, total_frames=100)  # len(variants) == 5
    assert first == wrapped


@patch("backend.services.video_composer.run_ffmpeg")
def test_build_scene_clip_passes_variant_specific_filter(mock_run_ffmpeg, tmp_path: Path):
    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"fake")
    out_path = tmp_path / "clip.mp4"

    video_composer._build_scene_clip(image_path, 4.0, out_path, variant=2)

    args = mock_run_ffmpeg.call_args[0][0]
    vf_index = args.index("-vf")
    filter_str = args[vf_index + 1]
    z, x, y = video_composer._ken_burns_expr(2, total_frames=round(4.0 * video_composer._FPS))
    assert f"z='{z}'" in filter_str
    assert f"x='{x}'" in filter_str


@patch("backend.services.video_composer.run_ffmpeg")
def test_compose_uses_a_different_motion_variant_per_scene(mock_run_ffmpeg, sample_scene_assets: list[SceneAssets], tmp_path: Path):
    for asset in sample_scene_assets:
        Path(asset.audio_path).write_bytes(b"fake")
        Path(asset.image_path).write_bytes(b"fake")

    job_dir = tmp_path / "job"
    video_composer.compose(sample_scene_assets, job_dir)

    ken_burns_calls = [c for c in mock_run_ffmpeg.call_args_list if "ken_burns" in c.kwargs["stage"]]
    filters = [c.args[0][c.args[0].index("-vf") + 1] for c in ken_burns_calls]
    assert len(set(filters)) == len(sample_scene_assets)  # each scene got a distinct motion


@patch("backend.services.video_composer.run_ffmpeg")
def test_compose_calls_ffmpeg_for_every_stage(mock_run_ffmpeg, sample_scene_assets: list[SceneAssets], tmp_path: Path):
    for asset in sample_scene_assets:
        Path(asset.audio_path).write_bytes(b"fake")
        Path(asset.image_path).write_bytes(b"fake")

    job_dir = tmp_path / "job"
    result = video_composer.compose(sample_scene_assets, job_dir)

    assert result == job_dir / "final.mp4"
    stages_called = [call.kwargs["stage"] for call in mock_run_ffmpeg.call_args_list]
    assert any("ken_burns" in s for s in stages_called)
    assert any("crossfade" in s for s in stages_called)  # video: crossfade, not a hard-cut concat
    assert any("concat" in s for s in stages_called)  # audio still uses plain concat
    assert any("captions" in s for s in stages_called)
    assert any("mix" in s for s in stages_called)


@patch("backend.services.video_composer.run_ffmpeg")
def test_compose_extends_non_last_clips_for_transition_overlap(mock_run_ffmpeg, sample_scene_assets: list[SceneAssets], tmp_path: Path):
    # Each non-last clip must be rendered TRANSITION_DURATION seconds longer
    # than its nominal scene duration, so the xfade overlap has real extra
    # footage to consume instead of visibly cutting the scene short.
    for asset in sample_scene_assets:
        Path(asset.audio_path).write_bytes(b"fake")
        Path(asset.image_path).write_bytes(b"fake")

    job_dir = tmp_path / "job"
    video_composer.compose(sample_scene_assets, job_dir)

    # Scene clips render in parallel, so pick each call by its output file, not by call order.
    ken_burns_calls = {
        Path(c.args[0][-1]).name: c.args[0] for c in mock_run_ffmpeg.call_args_list if "ken_burns" in c.kwargs["stage"]
    }
    ordered = sorted(sample_scene_assets, key=lambda s: s.index)
    first_clip_args = ken_burns_calls[f"scene_{ordered[0].index:02d}_clip.mp4"]
    last_clip_args = ken_burns_calls[f"scene_{ordered[-1].index:02d}_clip.mp4"]
    first_t_index = first_clip_args.index("-t")
    last_t_index = last_clip_args.index("-t")

    expected_first = sample_scene_assets[0].duration_seconds + video_composer._TRANSITION_DURATION_SECONDS
    expected_last = sample_scene_assets[-1].duration_seconds  # last clip: NOT extended

    assert float(first_clip_args[first_t_index + 1]) == expected_first
    assert float(last_clip_args[last_t_index + 1]) == expected_last


@patch("backend.services.video_composer.run_ffmpeg")
def test_crossfade_video_offsets_by_cumulative_nominal_durations(mock_run_ffmpeg, tmp_path: Path):
    clips = [tmp_path / f"c{i}.mp4" for i in range(3)]
    durations = [4.0, 5.0, 3.5]

    video_composer._crossfade_video(clips, durations, tmp_path / "out.mp4")

    args = mock_run_ffmpeg.call_args[0][0]
    filter_complex = args[args.index("-filter_complex") + 1]
    # transition 1 starts at the end of clip 0 (4.0s); transition 2 starts
    # at the end of clip 0+1 (9.0s) - both using the ORIGINAL nominal
    # durations, not the extended render durations, so the combined output
    # duration ends up as exactly sum(durations) with no drift.
    assert "offset=4.0" in filter_complex
    assert "offset=9.0" in filter_complex


def test_crossfade_video_uses_varied_transition_styles(tmp_path: Path):
    with patch("backend.services.video_composer.run_ffmpeg") as mock_run_ffmpeg:
        clips = [tmp_path / f"c{i}.mp4" for i in range(4)]
        durations = [3.0, 3.0, 3.0, 3.0]
        video_composer._crossfade_video(clips, durations, tmp_path / "out.mp4")

    filter_complex = mock_run_ffmpeg.call_args[0][0][mock_run_ffmpeg.call_args[0][0].index("-filter_complex") + 1]
    styles_used = {style for style in video_composer._TRANSITION_STYLES if f"transition={style}" in filter_complex}
    assert len(styles_used) >= 2  # not every transition uses the same style


def test_compose_raises_on_empty_scenes(tmp_path: Path):
    from backend.core.exceptions import CompositionError
    import pytest

    with pytest.raises(CompositionError):
        video_composer.compose([], tmp_path)


def test_select_motion_scene_positions_picks_first_and_last():
    assert video_composer._select_motion_scene_positions(5, max_count=2) == {0, 4}


def test_select_motion_scene_positions_all_scenes_when_budget_covers_all():
    # MotionTier.MAX: budget >= scene_count must select every scene, not
    # just opening+closing.
    assert video_composer._select_motion_scene_positions(5, max_count=5) == {0, 1, 2, 3, 4}
    assert video_composer._select_motion_scene_positions(3, max_count=10) == {0, 1, 2}


def test_motion_budget_for_tier():
    from backend.models.schemas import MotionTier

    with patch("backend.services.video_composer.settings") as mock_settings:
        mock_settings.magic_hour_max_scenes_per_job = 2
        assert video_composer._motion_budget_for_tier(MotionTier.MAX, 5) == 5
        assert video_composer._motion_budget_for_tier(MotionTier.BALANCED, 5) == 2
        assert video_composer._motion_budget_for_tier(MotionTier.BASIC, 5) == 0


def test_select_motion_scene_positions_respects_max_count_of_one():
    assert video_composer._select_motion_scene_positions(5, max_count=1) == {0}


def test_select_motion_scene_positions_disabled_when_zero():
    assert video_composer._select_motion_scene_positions(5, max_count=0) == set()


def test_select_motion_scene_positions_single_scene():
    assert video_composer._select_motion_scene_positions(1, max_count=2) == {0}


@patch("backend.services.video_composer._build_scene_clip")
@patch("backend.services.video_composer._build_motion_clip")
@patch("backend.services.video_composer.settings")
@patch("backend.services.video_composer.run_ffmpeg")
def test_compose_uses_motion_for_selected_scenes_when_key_configured(
    mock_run_ffmpeg, mock_settings, mock_build_motion, mock_build_ken_burns,
    sample_scene_assets: list[SceneAssets], tmp_path: Path,
):
    for asset in sample_scene_assets:
        Path(asset.audio_path).write_bytes(b"fake")
        Path(asset.image_path).write_bytes(b"fake")

    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    mock_settings.eightscale_key_pool = []
    mock_settings.magic_hour_key_pool = ["fake-key"]
    mock_settings.magic_hour_max_scenes_per_job = 2

    job_dir = tmp_path / "job"
    video_composer.compose(sample_scene_assets, job_dir)

    # 2 scenes in the fixture, max_count=2 -> both scenes (0 and 1, i.e.
    # first-and-last for a 2-scene job) should attempt motion generation.
    assert mock_build_motion.call_count == 2
    mock_build_ken_burns.assert_not_called()


@patch("backend.services.video_composer._build_scene_clip")
@patch("backend.services.video_composer._build_motion_clip")
@patch("backend.services.video_composer.settings")
@patch("backend.services.video_composer.run_ffmpeg")
def test_compose_falls_back_to_ken_burns_when_motion_fails(
    mock_run_ffmpeg, mock_settings, mock_build_motion, mock_build_ken_burns,
    sample_scene_assets: list[SceneAssets], tmp_path: Path,
):
    for asset in sample_scene_assets:
        Path(asset.audio_path).write_bytes(b"fake")
        Path(asset.image_path).write_bytes(b"fake")

    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    mock_settings.eightscale_key_pool = []
    mock_settings.magic_hour_key_pool = ["fake-key"]
    mock_settings.magic_hour_max_scenes_per_job = 2
    mock_build_motion.side_effect = RuntimeError("magic hour quota exhausted")

    job_dir = tmp_path / "job"
    video_composer.compose(sample_scene_assets, job_dir)

    assert mock_build_motion.call_count == 2
    assert mock_build_ken_burns.call_count == 2  # every motion attempt failed, Ken Burns covers all


@patch("backend.services.video_composer._build_scene_clip")
@patch("backend.services.video_composer._build_motion_clip")
@patch("backend.services.video_composer.settings")
@patch("backend.services.video_composer.run_ffmpeg")
def test_compose_skips_motion_when_no_key_configured(
    mock_run_ffmpeg, mock_settings, mock_build_motion, mock_build_ken_burns,
    sample_scene_assets: list[SceneAssets], tmp_path: Path,
):
    for asset in sample_scene_assets:
        Path(asset.audio_path).write_bytes(b"fake")
        Path(asset.image_path).write_bytes(b"fake")

    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    mock_settings.eightscale_key_pool = []
    mock_settings.magic_hour_key_pool = []
    mock_settings.magic_hour_max_scenes_per_job = 2

    job_dir = tmp_path / "job"
    video_composer.compose(sample_scene_assets, job_dir)

    mock_build_motion.assert_not_called()
    assert mock_build_ken_burns.call_count == 2
