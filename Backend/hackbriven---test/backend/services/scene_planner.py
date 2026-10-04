from __future__ import annotations

from backend.models.schemas import ScenePlan, ScenePlanSet, Script

STAGE = "intelligence.scene_planner"


def plan(script: Script) -> ScenePlanSet:
    """Derive a deterministic per-scene execution plan from a validated Script.

    Pure function: no I/O, no external calls. Same script in -> same plan out.
    """
    plans: list[ScenePlan] = []
    offset = 0.0
    for scene in sorted(script.scenes, key=lambda s: s.index):
        start = offset
        end = offset + scene.duration_seconds
        plans.append(
            ScenePlan(
                index=scene.index,
                narration=scene.narration,
                image_prompt=scene.image_prompt,
                duration_seconds=scene.duration_seconds,
                start_offset_seconds=start,
                end_offset_seconds=end,
            )
        )
        offset = end

    return ScenePlanSet(topic=script.topic, hook=script.hook, scenes=plans)
