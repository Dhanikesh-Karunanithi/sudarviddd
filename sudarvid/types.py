from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ThemeId(str, Enum):
    MODERN_NEWSPAPER = "modern_newspaper"
    SHARP_MINIMALISM = "sharp_minimalism"
    YELLOW_BLACK = "yellow_black"
    BLACK_ORANGE = "black_orange"
    MANGA = "manga"
    MAGAZINE = "magazine"
    NEO_RETRO_DEV = "neo_retro_dev"
    PINK_STREET = "pink_street"
    MINCHO_HANDWRITTEN = "mincho_handwritten"
    SEMINAR_MINIMAL = "seminar_minimal"
    ROYAL_BLUE_RED = "royal_blue_red"
    STUDIO_PREMIUM = "studio_premium"
    SPORTS = "sports"
    CLASSIC_POP = "classic_pop"
    TECH_NEON = "tech_neon"
    DIGITAL_NEO_POP = "digital_neo_pop"
    ANTI_GRAVITY = "anti_gravity"
    DEFORMED_PERSONA = "deformed_persona"


class AnimationLevel(str, Enum):
    SUBTLE = "subtle"
    MEDIUM = "medium"
    DYNAMIC = "dynamic"


@dataclass
class VideoSize:
    width: int
    height: int


@dataclass
class SlideContent:
    index: int
    title: str
    bullets: List[str]
    narration: str
    image_prompt: str
    image_path: Optional[str] = None
    duration_seconds: float = 5.0
    # Layout / learning UX (see content_planner JSON schema)
    layout_kind: str = "standard"
    # LLM-selected frame: where the generated image appears (HTML templates).
    visual_template: str = "full_bleed_bg"
    subtitle: Optional[str] = None
    learning_point: Optional[str] = None
    big_stat: Optional[str] = None
    stat_caption: Optional[str] = None


@dataclass
class GenerationConfig:
    topic: str
    audience: str
    language: str
    theme: ThemeId
    slide_count: int
    video_size: VideoSize
    animation_level: AnimationLevel
    include_tts: bool
    include_music: bool
    output_html: bool
    output_mp4: bool
    target_duration_seconds: Optional[float] = None
    custom_content: Optional[str] = None
    # Pedagogy / curriculum context (optional; used by ByteOS and CLI)
    learning_objectives: Optional[str] = None
    difficulty: Optional[str] = None
    source_notes: Optional[str] = None
    constraints: Optional[str] = None
    # Narrator/teacher voice (not the subject matter). When set, all slide copy and narration use this persona.
    persona: Optional[str] = None
    # edge-tts voice name, e.g. en-US-GuyNeural; when None, language default applies.
    voice_override: Optional[str] = None

