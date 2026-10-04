from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from backend.core.exceptions import CompositionError
from backend.core import plans
from backend.services import upscaler
from backend.utils.ffmpeg_utils import run_ffmpeg

STAGE = "composition.export"


@dataclass(frozen=True)
class Format:
    id: str
    label: str
    ext: str
    description: str
    kind: str  # "video" | "animation" | "audio"
    mime: str

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "ext": self.ext, "description": self.description, "kind": self.kind}


FORMATS: tuple[Format, ...] = (
    Format("mp4", "MP4", "mp4", "H.264 + AAC. Plays everywhere: phones, social apps, the web.", "video", "video/mp4"),
    Format("mov", "MOV", "mov", "QuickTime container for Apple devices and editing apps.", "video", "video/quicktime"),
    Format("webm", "WebM", "webm", "VP9 + Opus, optimised for websites.", "video", "video/webm"),
    Format("mkv", "MKV", "mkv", "Matroska container, popular for archiving.", "video", "video/x-matroska"),
    Format("gif", "GIF", "gif", "Silent looping preview of the first 12 seconds.", "animation", "image/gif"),
    Format("mp3", "MP3 audio", "mp3", "Narration and music only.", "audio", "audio/mpeg"),
)
_BY_ID = {f.id: f for f in FORMATS}

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def get_format(format_id: str) -> Format | None:
    return _BY_ID.get(format_id)


def _lock_for(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _convert(src: Path, fmt: Format, dst: Path) -> None:
    if fmt.id in ("mov", "mkv"):
        # Same H.264/AAC streams in a different container: lossless and instant.
        args = ["-i", str(src), "-c", "copy", "-movflags", "+faststart", str(dst)]
    elif fmt.id == "webm":
        args = [
            "-i", str(src),
            "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "0", "-row-mt", "1", "-deadline", "realtime", "-cpu-used", "8",
            "-c:a", "libopus", "-b:a", "128k",
            str(dst),
        ]
    elif fmt.id == "gif":
        args = [
            "-i", str(src), "-t", "12", "-an",
            "-vf", "fps=12,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
            "-loop", "0",
            str(dst),
        ]
    elif fmt.id == "mp3":
        args = ["-i", str(src), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(dst)]
    else:  # pragma: no cover - mp4 never reaches here
        raise CompositionError(STAGE, f"unsupported format {fmt.id}")
    run_ffmpeg(args, stage=f"{STAGE}.{fmt.id}")


def export_format(job_dir: Path, format_id: str) -> Path:
    """Return the job's video in the requested format, converting on first request and caching the
    result next to the master. MP4 is the stored master itself."""
    fmt = get_format(format_id)
    if fmt is None:
        raise CompositionError(STAGE, f"unknown format {format_id!r}")
    master = job_dir / "final.mp4"
    if not master.exists():
        raise CompositionError(STAGE, "no video to export yet")
    if fmt.id == "mp4":
        return master

    out_dir = job_dir / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"video.{fmt.ext}"
    with _lock_for(str(dst)):  # two simultaneous clicks must not run the same conversion twice
        if dst.exists() and dst.stat().st_size > 0 and dst.stat().st_mtime >= master.stat().st_mtime:
            return dst
        tmp = out_dir / f"video.partial.{fmt.ext}"
        tmp.unlink(missing_ok=True)
        try:
            _convert(master, fmt, tmp)
            os.replace(tmp, dst)
        finally:
            tmp.unlink(missing_ok=True)
    return dst


def deliver_at_resolution(job_dir: Path, composed: Path, resolution_id: str) -> Path:
    """Turn the composer's 1080p output into the delivery the user asked for. The 1080p master is
    kept as final_1080p.mp4; `final.mp4` always holds what is delivered (and what every other
    format is converted from)."""
    resolution = plans.resolution_def(resolution_id)
    if resolution is None:
        raise CompositionError(STAGE, f"unknown resolution {resolution_id!r}")
    if resolution.id == "1080p":
        return composed

    master_1080 = job_dir / "final_1080p.mp4"
    shutil.copyfile(composed, master_1080)
    delivered = job_dir / "final_delivery.mp4"
    delivered.unlink(missing_ok=True)

    if resolution.id == "720p":
        run_ffmpeg(
            [
                "-i", str(master_1080),
                "-vf", f"scale={resolution.width}:{resolution.height}:flags=lanczos,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-c:a", "copy", "-movflags", "+faststart",
                str(delivered),
            ],
            stage=f"{STAGE}.720p",
        )
    else:
        upscaler.enhance_video(master_1080, delivered, width=resolution.width, height=resolution.height)

    os.replace(delivered, composed)
    return composed
