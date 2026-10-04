from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frontend.app import _render_status


def test_render_status_marks_completed_stages_done():
    rendered = _render_status("running_composition")
    assert "[x] Queued" in rendered
    assert "[x] Script" in rendered
    assert "[x] Visuals & Voice" in rendered
    assert "**Composition (running)**" in rendered
    assert "[ ] Quality Check" in rendered


def test_render_status_all_done():
    rendered = _render_status("done")
    assert rendered.count("[x]") == 6
    assert "[ ]" not in rendered


def test_render_status_failed():
    rendered = _render_status("failed")
    assert "**Failed**" in rendered
