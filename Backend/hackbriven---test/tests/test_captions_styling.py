from pathlib import Path

from backend.models.schemas import CaptionSettings, CaptionWord, Language, SceneAssets
from backend.services import captions, video_composer
from backend.services.caption_generator import spread_words


def _scene(index, words, duration):
    return SceneAssets(
        index=index,
        image_path="",
        audio_path="",
        duration_seconds=duration,
        caption_words=[CaptionWord(word=w, start_seconds=s, end_seconds=e) for w, s, e in words],
    )


def _dialogues(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("Dialogue:")]


def test_words_stay_on_screen_until_the_next_word(tmp_path: Path):
    scene = _scene(0, [("one", 0.0, 0.2), ("two", 0.5, 0.7), ("three", 1.0, 1.2)], 3.0)
    lines = _dialogues(video_composer.build_ass_captions([scene], tmp_path / "c.ass"))
    assert lines[0].startswith("Dialogue: 0,0:00:00.00,0:00:00.50,")  # held until "two" starts
    assert lines[1].startswith("Dialogue: 0,0:00:00.50,0:00:01.00,")
    assert ",0:00:01.80," in lines[2]  # last word held 0.6s after it ends


def test_hold_never_runs_past_the_scene(tmp_path: Path):
    first = _scene(0, [("end", 0.0, 0.9)], 1.0)
    second = _scene(1, [("next", 0.1, 0.3)], 1.0)
    lines = _dialogues(video_composer.build_ass_captions([first, second], tmp_path / "c.ass"))
    assert lines[0].startswith("Dialogue: 0,0:00:00.00,0:00:01.00,")
    assert lines[1].startswith("Dialogue: 0,0:00:01.10,")


def test_style_sets_size_and_colours(tmp_path: Path):
    style = CaptionSettings(size="large", color="#112233", highlight="#FF0000")
    text = video_composer.build_ass_captions([_scene(0, [("hi", 0, 0.5)], 1.0)], tmp_path / "c.ass", style=style).read_text(
        encoding="utf-8"
    )
    assert "&H00332211" in text  # text colour as ASS BGR
    assert "{\\c&H000000FF&}hi" in text  # highlight colour on the spoken word


def test_spread_words_covers_span_in_order():
    words = spread_words("a bb ccc", 1.0, 4.0)
    assert [w.word for w in words] == ["a", "bb", "ccc"]
    assert words[0].start_seconds == 1.0
    assert abs(words[-1].end_seconds - 4.0) < 0.01
    assert all(a.end_seconds <= b.start_seconds + 1e-6 for a, b in zip(words, words[1:]))


def test_display_scenes_same_language_keeps_spoken_words(tmp_path: Path):
    captions.save_source(tmp_path, [_scene(0, [("hello", 0.1, 0.4)], 1.0)], {0: "hello"})
    scenes = captions.display_scenes(captions.load_source(tmp_path), CaptionSettings(), Language.EN)
    assert [w.word for w in scenes[0].caption_words] == ["hello"]


def test_display_scenes_translates_and_times_within_speech(tmp_path: Path, monkeypatch):
    captions.save_source(tmp_path, [_scene(0, [("hello", 0.2, 0.4), ("world", 0.5, 0.9)], 1.5)], {0: "hello world"})
    monkeypatch.setattr(captions.caption_translator, "translate_lines", lambda lines, target: ["नमस्ते दुनिया"])
    scenes = captions.display_scenes(captions.load_source(tmp_path), CaptionSettings(language="hi"), Language.EN)
    words = scenes[0].caption_words
    assert [w.word for w in words] == ["नमस्ते", "दुनिया"]
    assert words[0].start_seconds == 0.2 and abs(words[-1].end_seconds - 0.9) < 0.01
