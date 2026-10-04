from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.models.schemas import Job

STAGE = "publishing.qoneqt_handoff"

# Qoneqt has no public creator-publishing API (confirmed by reading the
# Content Creators roster spreadsheet the client provided: it is a manually
# maintained creator list + hand-typed daily engagement tracker, not an API
# integration). Every "publish" on this platform is therefore this honest
# manual handoff, never a real PUBLISHED status - see RULES.md and PRD 6.7:
# "do not claim successful publishing until the platform confirms success."

_NOTE_TEMPLATE = """\
QONEQT MANUAL PUBLISH HANDOFF
==============================
This video was NOT automatically published. Qoneqt does not currently expose
a public API for posting to a creator's feed, so this package is a manual
handoff: hand the video below to a creator from your Content Creators roster
to post manually through their own Qoneqt account.

Job ID:         {job_id}
Generated at:   {generated_at}
Language:       {language}
Motion tier:    {motion_tier}

Suggested title:
{title}

Suggested caption / hook:
{hook}

Video file:
{video_path}

Next step: assign this to a creator from your Content Creators roster and have
them post it manually. Once posted, record the resulting Qoneqt post URL
yourself - this tool has no way to verify or fetch it automatically.
"""


def build_handoff(job: Job, job_dir: Path) -> tuple[Path, str]:
    """Write a handoff note next to the job's final video and return
    (note_path, note_text). Never renames/moves the video - the handoff is
    additive, the final.mp4 stays exactly where quality_gate validated it."""
    if not job.result_path:
        raise ValueError("job has no result_path - cannot build a publish handoff for an unrendered job")

    title = (job.script.hook if job.script else job.topic)[:100]
    hook = job.script.hook if job.script else job.topic

    note_text = _NOTE_TEMPLATE.format(
        job_id=job.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        language=job.language.value,
        motion_tier=job.motion_tier.value,
        title=title,
        hook=hook,
        video_path=job.result_path,
    )

    note_path = job_dir / "qoneqt_handoff.txt"
    note_path.write_text(note_text, encoding="utf-8")
    return note_path, note_text
