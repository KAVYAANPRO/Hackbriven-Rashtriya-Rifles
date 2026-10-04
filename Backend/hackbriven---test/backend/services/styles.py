from __future__ import annotations

from dataclasses import dataclass

"""Video style presets (the Canva-style "make it minimalistic / playful / 3D /
colourful" choice).

A style does three jobs, all driven from this one table so the UI and the
pipeline can never disagree about what a style means:
  * `tone`   - how the script writer should sound (given to the LLM),
  * `visual` - the art direction appended to every scene's image prompt,
  * `mood`   - nudges the generated background music (upbeat vs calm).
"""

COMMON_VISUAL_RULES = (
    "vertical 9:16 composition, main subject centered with room around it, "
    "no text, no captions, no logos, no watermark"
)


@dataclass(frozen=True)
class Style:
    id: str
    label: str
    description: str
    group: str
    tone: str
    visual: str
    mood: str  # "upbeat" | "calm" | "" (leave to the script)

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "description": self.description, "group": self.group}


STYLES: tuple[Style, ...] = (
    Style("auto", "Auto", "Let the AI pick what fits the topic", "Classic", "", "", ""),
    Style(
        "cinematic", "Cinematic", "Film-like light, drama and depth", "Classic",
        "Dramatic, atmospheric, trailer-like narration with a confident pace.",
        "cinematic film still, dramatic lighting, shallow depth of field, anamorphic lens look, rich colour grading",
        "calm",
    ),
    Style(
        "documentary", "Documentary", "Natural, real and observational", "Classic",
        "Grounded, curious and factual, like a good documentary narrator.",
        "documentary photography, natural light, candid realistic moment, fine film grain",
        "calm",
    ),
    Style(
        "news", "News", "Clear, neutral and broadcast-like", "Classic",
        "Neutral, precise and clear, like a news presenter; no hype.",
        "broadcast news look, neutral even lighting, clean documentary framing, realistic",
        "calm",
    ),
    Style(
        "educational", "Educational", "Simple visuals that explain", "Classic",
        "Friendly and clear: explain step by step, one idea per scene.",
        "clean flat infographic-style vector illustration, simple friendly shapes, bright clean background, easy to read at a glance",
        "calm",
    ),
    Style(
        "corporate", "Corporate", "Polished, professional, trustworthy", "Classic",
        "Professional, confident and concise; avoid slang.",
        "clean corporate style, modern professional setting, soft blue and white palette, tidy composition",
        "calm",
    ),
    Style(
        "minimalist", "Minimalist", "Calm, clean and full of space", "Creative",
        "Calm and spare: short sentences, no filler words.",
        "minimalist flat design, one simple subject, generous empty negative space, soft neutral pastel palette, clean geometric shapes, no clutter",
        "calm",
    ),
    Style(
        "playful", "Playful", "Fun, bouncy and bright", "Creative",
        "Lively, witty and upbeat with short punchy sentences and light humour.",
        "playful flat vector cartoon illustration, bright cheerful colours, thick clean outlines, rounded friendly shapes, whimsical, not a photograph",
        "upbeat",
    ),
    Style(
        "3d", "3D", "Glossy 3D renders with depth", "Creative",
        "Energetic and modern, like a product reveal.",
        "stylized 3D animated render, Pixar and Blender look, octane render, smooth clay-like plastic materials, soft studio lighting, cute rounded shapes, not a photograph",
        "upbeat",
    ),
    Style(
        "colorful", "Colorful", "Vibrant, saturated, high energy", "Creative",
        "High-energy and enthusiastic; keep the momentum up.",
        "vibrant pop-art graphic style, bold saturated colour blocking, high contrast, energetic and eye-catching",
        "upbeat",
    ),
    Style(
        "illustrated", "Illustrated", "Hand-drawn storybook look", "Creative",
        "Warm and story-like, as if reading from a picture book.",
        "hand-drawn storybook illustration, watercolour and ink, soft pastel palette, visible brush texture, not a photograph",
        "calm",
    ),
    Style(
        "retro", "Retro", "Vintage 80s and 90s vibe", "Creative",
        "Nostalgic and a little cheeky.",
        "1980s retro poster art, vintage print texture, film grain, faded warm colours",
        "upbeat",
    ),
    Style(
        "neon", "Neon", "Glowing cyberpunk nights", "Creative",
        "Fast, edgy and futuristic.",
        "neon cyberpunk digital art, glowing magenta and cyan lights, wet night streets, high contrast",
        "upbeat",
    ),
    Style(
        "dark", "Dark and moody", "Low-key light, deep shadows", "Creative",
        "Serious, intense and a little mysterious.",
        "dark moody atmosphere, low-key lighting, deep shadows, teal and amber accents, subtle haze",
        "calm",
    ),
    Style("custom", "Custom", "Describe your own look", "Custom", "", "", ""),
)

_BY_ID = {s.id: s for s in STYLES}
MAX_CUSTOM_CHARS = 300


def get(style_id: str) -> Style | None:
    return _BY_ID.get(style_id)


def is_valid(style_id: str) -> bool:
    return style_id in _BY_ID


def clean_custom(text: str | None) -> str:
    """User-written style text goes straight into LLM and image prompts, so keep it to plain, bounded text."""
    return " ".join((text or "").split())[:MAX_CUSTOM_CHARS]


def tone_for(style_id: str, custom: str | None = None) -> str:
    style = _BY_ID.get(style_id)
    if style is None or style.id == "auto":
        return ""
    if style.id == "custom":
        text = clean_custom(custom)
        return f"Match this requested style and feel: {text}." if text else ""
    return style.tone


def visual_for(style_id: str, custom: str | None = None) -> str:
    """The art direction to append to a scene's image prompt ('' for auto)."""
    style = _BY_ID.get(style_id)
    if style is None or style.id == "auto":
        return ""
    if style.id == "custom":
        text = clean_custom(custom)
        return f"{text}, {COMMON_VISUAL_RULES}" if text else ""
    return f"{style.visual}, {COMMON_VISUAL_RULES}"


def _direction(style_id: str, custom: str | None) -> str:
    style = _BY_ID.get(style_id)
    if style is None or style.id == "auto":
        return ""
    if style.id == "custom":
        return clean_custom(custom)
    return style.visual


def apply_to_image_prompt(prompt: str, style_id: str, custom: str | None = None) -> str:
    """The final prompt sent to the image model. FLUX gives the most weight to what comes first, so
    the chosen style leads the prompt and is restated at the end - otherwise a "3D" or "minimal"
    request gets drowned out by a long, photographic scene description."""
    scene = prompt.strip().rstrip(".")
    direction = _direction(style_id, custom)
    if not direction:
        return f"{scene}, {COMMON_VISUAL_RULES}"
    return f"{direction}. {scene}. Rendered entirely in this style: {direction}, {COMMON_VISUAL_RULES}"


def music_mood(style_id: str) -> str:
    style = _BY_ID.get(style_id)
    return style.mood if style else ""
