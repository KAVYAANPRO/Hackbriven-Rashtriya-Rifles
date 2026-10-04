from __future__ import annotations

import json
from pathlib import Path

from backend.models.schemas import CaptionSettings, CaptionWord, Language, SceneAssets
from backend.services import caption_translator
from backend.services.caption_generator import spread_words

SOURCE_FILE = "captions.json"


def save_source(job_dir: Path, assets: list[SceneAssets], narrations: dict[int, str]) -> None:
    """Keep what is needed to re-burn captions later (timings, durations, script text)."""
    data = [
        {
            "index": a.index,
            "duration": a.duration_seconds,
            "narration": narrations.get(a.index, ""),
            "words": [w.model_dump() for w in a.caption_words],
        }
        for a in sorted(assets, key=lambda a: a.index)
    ]
    (job_dir / SOURCE_FILE).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_source(job_dir: Path) -> list[dict]:
    return json.loads((job_dir / SOURCE_FILE).read_text(encoding="utf-8"))


def display_scenes(source: list[dict], style: CaptionSettings, narration_language: Language) -> list[SceneAssets]:
    """Per-scene caption words to burn in. Same language: the exact spoken words and timings.
    Another language: each scene's narration translated, timed across that scene's speech."""
    scenes = [
        SceneAssets(
            index=s["index"],
            image_path="",
            audio_path="",
            duration_seconds=s["duration"],
            caption_words=[CaptionWord(**w) for w in s["words"]],
        )
        for s in source
    ]
    if style.language in ("same", narration_language.value):
        return scenes

    translated = caption_translator.translate_lines([s.get("narration", "") for s in source], style.language)
    for scene, text in zip(scenes, translated):
        words = scene.caption_words
        start = words[0].start_seconds if words else 0.05
        end = words[-1].end_seconds if words else max(0.1, scene.duration_seconds - 0.05)
        scene.caption_words = spread_words(text, start, end)
    return scenes
