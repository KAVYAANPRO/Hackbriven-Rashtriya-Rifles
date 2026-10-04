from __future__ import annotations

from pathlib import Path

import pytest

from backend.models.schemas import Job, Language, MotionTier, Script
from backend.services import qoneqt_handoff


def _job(**overrides) -> Job:
    defaults = dict(topic="Why EVs are popular", result_path="/tmp/final.mp4")
    defaults.update(overrides)
    return Job(**defaults)


def test_build_handoff_requires_result_path(tmp_path: Path) -> None:
    job = Job(topic="no video yet")
    with pytest.raises(ValueError):
        qoneqt_handoff.build_handoff(job, tmp_path)


def test_build_handoff_writes_note_file(tmp_path: Path) -> None:
    job = _job(language=Language.HI, motion_tier=MotionTier.MAX)
    note_path, note_text = qoneqt_handoff.build_handoff(job, tmp_path)

    assert note_path.exists()
    assert note_path.read_text(encoding="utf-8") == note_text
    assert "NOT automatically published" in note_text
    assert job.id in note_text
    assert "hi" in note_text
    assert "max" in note_text


def test_build_handoff_uses_script_hook_when_available(tmp_path: Path) -> None:
    script = Script(topic="t", hook="EVs are taking over the roads.", scenes=[])
    job = _job(script=script)

    _, note_text = qoneqt_handoff.build_handoff(job, tmp_path)

    assert "EVs are taking over the roads." in note_text


def test_build_handoff_falls_back_to_topic_without_script(tmp_path: Path) -> None:
    job = _job(topic="Will EV cars take over?")

    _, note_text = qoneqt_handoff.build_handoff(job, tmp_path)

    assert "Will EV cars take over?" in note_text
