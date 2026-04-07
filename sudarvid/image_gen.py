from __future__ import annotations

import base64
import os
import random
import re
import sys
import time
from typing import Callable, List, Optional

import requests

from .themes import get_theme
from .types import GenerationConfig, SlideContent, ThemeId
from .image_models import DEFAULT_IMAGE_MODEL


# Bias toward scenes the diffusion model can render without lettering; avoid poster/magazine wording.
THEME_STYLE_SNIPPETS = {
    "modern_newspaper": (
        "Swiss editorial photography feel, monochrome cutout subjects, cool gray or white studio backdrop, "
        "jet black accents, asymmetric composition, still-life clarity"
    ),
    "sharp_minimalism": (
        "ultra-clean Swiss minimal, pure white field, razor-thin black lines, simple geometric shapes, no symbols"
    ),
    "yellow_black": (
        "high-contrast yellow and black field, bold geometric blocks, stadium energy, abstract shapes only"
    ),
    "black_orange": (
        "crisp white canvas, electric orange accent geometry, black line art, product-still crispness"
    ),
    "manga": (
        "Japanese comic ink lines, screentone texture, expressive motion lines, limited flat color fills"
    ),
    "magazine": (
        "warm paper-toned studio photograph, soft duotone lighting, fashion-adjacent still life, shallow depth"
    ),
    "neo_retro_dev": (
        "neo-retro scene, off-white grid paper texture, thick black borders, hot pink and cyan blocks, toy-like props"
    ),
    "pink_street": (
        "urban daylight scene, hot pink sky wash, bold silhouettes, candid street photography mood"
    ),
    "mincho_handwritten": (
        "Japanese ink-wash illustration, warm yellow paper texture, red accent brushstroke, single calm subject"
    ),
    "seminar_minimal": (
        "academic calm, white field, crimson accent lines, empty lecture-hall still life"
    ),
    "royal_blue_red": (
        "institutional palette, soft blue-gray ground, royal blue and deep red props, balanced studio setup"
    ),
    "studio_premium": (
        "premium keynote mood, soft gray-white studio, violet and gold light, glass objects and reflections"
    ),
    "sports": (
        "broadcast energy, deep black field, neon lime and orange light streaks, abstract motion, no logos"
    ),
    "classic_pop": (
        "retro pop-art color fields, magenta and cyan gradients, halftone texture as abstract pattern only"
    ),
    "tech_neon": (
        "retro tech mood, pale sage wall, acid yellow practical lights, physical knobs and cables, no screens"
    ),
    "digital_neo_pop": (
        "clean white studio, magenta and cyan light gradients, crisp 3D primitives, soft shadows"
    ),
    "anti_gravity": (
        "minimal airy scene, pure white background, soft cyan-violet rim light, floating translucent objects"
    ),
    "deformed_persona": (
        "soft illustrated scene, warm parchment ground, muted sage and clay tones, gentle character silhouette"
    ),
}

# Some Together image models ignore negative_prompt; strong positive + sanitization still help.
NEGATIVE_PROMPT_TEXT_FREE = (
    "text, letters, words, typography, caption, subtitle, logo, watermark, signature, symbols, glyphs, "
    "infographic, diagram, chart, plot, axes, labels, map labels, street signs, book pages, newspaper, "
    "handwriting, HUD, UI, screenshot, interface mockup, scientific figure, equation"
)

# Phrases that invite illegible generated text; stripped from planner-provided prompts.
_FORBIDDEN_PROMPT_TOKENS = re.compile(
    r"(?i)\b("
    r"chart|diagram|infographic|labeled|labels|screenshot|mockup|mock-up|ui\b|ux\b|interface|"
    r"poster|newspaper|magazine cover|street sign|book page|map\b|typography|font\b|glyph|subtitle|"
    r"caption|watermark|logo|signage|hud|plot\b|axes|equation|scientific figure|"
    r"labeled diagram|flowchart"
    r")\b"
)


def _sanitize_image_prompt(base: str) -> str:
    """Remove wording that tends to produce on-image text or UI in diffusion models."""
    s = (base or "").strip()
    if not s:
        return s
    s = _FORBIDDEN_PROMPT_TOKENS.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:-")
    return s


def _image_steps_for_model(model: str) -> Optional[int]:
    """FLUX.2 rejects `steps`; others use TOGETHER_IMAGE_STEPS or default 6."""
    if "FLUX.2" in model:
        return None
    raw = os.environ.get("TOGETHER_IMAGE_STEPS", "").strip()
    if raw:
        try:
            return max(1, min(50, int(raw)))
        except ValueError:
            pass
    return 6


def _fit_dim_to_model_constraints(value: int) -> int:
    """
    Together image models often require:
    - height/width between 256 and 2048
    - multiples of 16
    """
    multiple = 16
    # Together models vary by model; FLUX.1-schnell in this SDK rejects >1792 width.
    min_v = 64
    max_v = 1792
    v = int(value)
    v = max(min_v, min(max_v, v))

    # Round to nearest multiple of 16 to preserve aspect ratio.
    v = int(round(v / multiple) * multiple)
    v = max(min_v, min(max_v, v))

    # Final guard: enforce exact multiple.
    if v % multiple != 0:
        v = (v // multiple) * multiple
        v = max(min_v, min(max_v, v))
    return v


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = (color or "#808080").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _generate_placeholder_image(output_path: str, slide_title: str, theme_id: ThemeId) -> None:
    """Minimal on-theme PNG when the image API fails after retries."""
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    spec = get_theme(theme_id.value)
    w, h = 1920, 1080
    bg = _hex_to_rgb(spec.bg_color)
    accent = _hex_to_rgb(spec.accent_color)
    fg = _hex_to_rgb(spec.text_color)
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([48, 48, w - 48, h - 48], outline=accent, width=10)
    label = (slide_title or "Slide")[:100]
    try:
        font = ImageFont.truetype("arial.ttf", 44)
    except OSError:
        font = ImageFont.load_default()
    draw.text((100, 100), label, fill=fg, font=font)
    img.save(output_path)


def build_image_prompt(theme_id: ThemeId, base_prompt: str) -> str:
    cleaned = _sanitize_image_prompt(base_prompt)
    if not cleaned:
        cleaned = "A single clear photographic or painterly scene with one focal subject"
    style = (THEME_STYLE_SNIPPETS.get(theme_id.value) or "").strip()
    lead = (
        f"A single photographic or painterly scene: {cleaned}. Style: {style}. "
        if style
        else f"A single photographic or painterly scene: {cleaned}. Clear focal subject, editorial composition. "
    )
    return (
        lead
        + "No text in the image — only environment, objects, or figures. "
        + "Absolutely no letters, words, captions, labels, logos, watermarks, signage, or screens with writing."
    )


class ImageGenerator:
    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        output_dir: str = "output/assets/images",
    ):
        self.api_key = api_key
        self.model = model or os.environ.get("TOGETHER_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _download_to_path(self, url: str, path: str) -> None:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)

    def _save_b64_to_path(self, b64_json: str, path: str) -> None:
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64_json))

    def generate_for_slides(
        self,
        config: GenerationConfig,
        slides: List[SlideContent],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[SlideContent]:
        updated: List[SlideContent] = []
        total = len(slides)
        job_seed = random.randint(1, 2**31 - 1)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = "https://api.together.xyz/v1/images/generations"

        for idx, slide in enumerate(slides, start=1):
            slide.image_path = None
            if getattr(slide, "layout_kind", None) in ("intro", "outro"):
                if progress_callback:
                    progress_callback(idx, total)
                updated.append(slide)
                continue
            if getattr(slide, "visual_template", None) == "none":
                if progress_callback:
                    progress_callback(idx, total)
                updated.append(slide)
                continue

            prompt = build_image_prompt(
                config.theme,
                slide.image_prompt or f"visual illustration for: {slide.title}",
            )
            filename = f"slide_{slide.index:02d}.png"
            out_path = os.path.join(self.output_dir, filename)

            ok = False
            last_err: Optional[Exception] = None
            for attempt in range(3):
                payload: dict = {
                    "model": self.model,
                    "prompt": prompt,
                    "negative_prompt": NEGATIVE_PROMPT_TEXT_FREE,
                    "width": _fit_dim_to_model_constraints(config.video_size.width),
                    "height": _fit_dim_to_model_constraints(config.video_size.height),
                    "n": 1,
                    "seed": (job_seed + slide.index) % (2**31),
                }
                steps = _image_steps_for_model(self.model)
                if steps is not None:
                    payload["steps"] = steps

                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=120)
                    if resp.status_code >= 400:
                        err_body = (resp.text or "")[:300]
                        if "seed" in err_body.lower() or resp.status_code == 422:
                            payload.pop("seed", None)
                            resp = requests.post(url, headers=headers, json=payload, timeout=120)
                    resp.raise_for_status()
                    data = resp.json()
                    data0 = (data.get("data") or [{}])[0]

                    if "url" in data0 and data0["url"]:
                        self._download_to_path(data0["url"], out_path)
                    elif "b64_json" in data0 and data0["b64_json"]:
                        self._save_b64_to_path(data0["b64_json"], out_path)
                    else:
                        raise RuntimeError(f"Unexpected Together images response shape: {data0.keys()}")

                    slide.image_path = out_path
                    ok = True
                    break
                except Exception as e:
                    last_err = e
                    if attempt < 2:
                        time.sleep(2**attempt)

            if not ok:
                print(
                    f"[SudarVid] WARNING: Image gen failed for slide {slide.index} after 3 attempts: {last_err}",
                    file=sys.stderr,
                )
                try:
                    _generate_placeholder_image(out_path, slide.title, config.theme)
                    slide.image_path = out_path
                except Exception as pe:
                    print(
                        f"[SudarVid] WARNING: Placeholder image failed for slide {slide.index}: {pe}",
                        file=sys.stderr,
                    )
            if progress_callback:
                progress_callback(idx, total)
            updated.append(slide)
        return updated
