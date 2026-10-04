from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter

"""Putting an arbitrary image into the video's vertical frame without ruining it.

Most image generators return a square (or landscape) picture, and a 9:16 video
frame is far narrower. Center-cropping a square to 9:16 throws away ~68% of the
picture - subjects get cut in half and the remainder is stretched ~2.5x, which
reads as blurry and glitchy. Instead, when the aspect ratio is far from the
frame's, show the WHOLE image sharp at full width, over a blurred, darkened,
zoomed copy of itself (the standard "blurred background" vertical-video look).
Images that are already close to 9:16 are simply cover-cropped.
"""

_NEAR_FRAME_TOLERANCE = 0.12  # relative aspect-ratio difference treated as "already vertical"


def cover_crop(image: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    resized = image.resize((max(width, round(src_w * scale)), max(height, round(src_h * scale))), Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def fit_to_frame(image: Image.Image, width: int, height: int) -> Image.Image:
    image = image.convert("RGB")
    frame_ratio = width / height
    ratio = image.width / image.height
    if abs(ratio - frame_ratio) / frame_ratio <= _NEAR_FRAME_TOLERANCE:
        return cover_crop(image, width, height)

    background = cover_crop(image, width, height).filter(ImageFilter.GaussianBlur(radius=max(12, width * 0.045)))
    background = ImageEnhance.Brightness(background).enhance(0.62)

    # Fit the whole image inside the frame (wider-than-frame images fill the width).
    if ratio > frame_ratio:
        fg_w, fg_h = width, max(1, round(width / ratio))
    else:
        fg_w, fg_h = max(1, round(height * ratio)), height
    foreground = image.resize((fg_w, fg_h), Image.LANCZOS)

    # Feather the foreground's top/bottom edges into the backdrop so there is no hard seam.
    feather = max(4, min(fg_h // 14, 40))
    mask = Image.new("L", (fg_w, fg_h), 255)
    for i in range(feather):
        value = round(255 * (i + 1) / (feather + 1))
        for y in (i, fg_h - 1 - i):
            mask.paste(value, (0, y, fg_w, y + 1))

    canvas = background.copy()
    canvas.paste(foreground, ((width - fg_w) // 2, (height - fg_h) // 2), mask)
    return canvas
