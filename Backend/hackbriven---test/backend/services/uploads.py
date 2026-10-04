from __future__ import annotations

import io
import json
import logging
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from backend.config import settings
from backend.services import framing

logger = logging.getLogger(__name__)

# Reference images become scene visuals, so they're normalised once at upload:
# decoded (proving they really are images), EXIF-rotated, stripped of metadata,
# and cover-cropped to the video's exact frame so the pipeline can use the
# stored file as-is.
_MAX_PIXELS = 60_000_000  # decompression-bomb guard, well above any real photo


class UploadError(Exception):
    """Carries an HTTP-ish status so the route can map it without string matching."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


def _dir() -> Path:
    path = settings.storage_path / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def path_for(upload_id: str) -> Path:
    # ids are generated here (uuid hex), but they also arrive from clients -
    # refuse anything that isn't one so an id can never address another path.
    if not upload_id.isalnum() or len(upload_id) != 32:
        raise UploadError(422, f"invalid reference image id: {upload_id!r}")
    return _dir() / f"{upload_id}.png"


def _meta_path(upload_id: str) -> Path:
    return _dir() / f"{upload_id}.json"


def _cover_crop(image: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    resized = image.resize((max(width, round(src_w * scale)), max(height, round(src_h * scale))), Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def save_image(account: str, filename: str, data: bytes) -> dict:
    if not data:
        raise UploadError(422, f"{filename} is empty")
    if len(data) > settings.max_upload_bytes:
        raise UploadError(413, f"{filename} is larger than {settings.max_upload_bytes // (1024 * 1024)} MB")

    Image.MAX_IMAGE_PIXELS = _MAX_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # structural check; the image must be re-opened to actually decode
        with Image.open(io.BytesIO(data)) as image:
            from PIL import ImageOps

            image = ImageOps.exif_transpose(image).convert("RGB")
            original_size = image.size
            framed = framing.fit_to_frame(image, settings.target_width, settings.target_height)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError, ValueError) as exc:
        raise UploadError(415, f"{filename} is not a readable image ({type(exc).__name__})") from exc

    upload_id = uuid.uuid4().hex
    framed.save(path_for(upload_id), format="PNG")
    _meta_path(upload_id).write_text(
        json.dumps({"owner": account, "name": filename[:200], "width": original_size[0], "height": original_size[1]}),
        encoding="utf-8",
    )
    return {
        "id": upload_id,
        "name": filename[:200],
        "size": len(data),
        "width": original_size[0],
        "height": original_size[1],
    }


def resolve(upload_ids: list[str], account: str) -> list[Path]:
    """Map client-supplied upload ids to files, refusing ids that don't exist
    or belong to another account."""
    paths: list[Path] = []
    for upload_id in upload_ids:
        image_path = path_for(upload_id)
        meta_path = _meta_path(upload_id)
        if not image_path.exists() or not meta_path.exists():
            raise UploadError(422, f"unknown reference image: {upload_id}")
        try:
            owner = json.loads(meta_path.read_text(encoding="utf-8")).get("owner")
        except (OSError, ValueError):
            owner = None
        if owner != account:
            raise UploadError(422, f"unknown reference image: {upload_id}")
        paths.append(image_path)
    return paths
