from __future__ import annotations

from backend.services import scene_planner
from backend.models.schemas import Script


def test_plan_produces_sequential_offsets(sample_script: Script) -> None:
    plan = scene_planner.plan(sample_script)

    assert len(plan.scenes) == 3
    assert plan.scenes[0].start_offset_seconds == 0.0
    assert plan.scenes[0].end_offset_seconds == 4.0
    assert plan.scenes[1].start_offset_seconds == 4.0
    assert plan.scenes[1].end_offset_seconds == 9.0
    assert plan.scenes[2].start_offset_seconds == 9.0
    assert plan.scenes[2].end_offset_seconds == 12.5
    assert plan.total_duration_seconds == 12.5


def test_plan_is_deterministic(sample_script: Script) -> None:
    first = scene_planner.plan(sample_script)
    second = scene_planner.plan(sample_script)
    assert first == second


def test_plan_handles_out_of_order_scenes(sample_script: Script) -> None:
    shuffled = sample_script.model_copy(
        update={"scenes": list(reversed(sample_script.scenes))}
    )
    plan = scene_planner.plan(shuffled)
    assert [s.index for s in plan.scenes] == [0, 1, 2]
