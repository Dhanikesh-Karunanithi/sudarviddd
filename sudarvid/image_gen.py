from __future__ import annotations

import base64
import os
import sys
from typing import List, Optional

import requests

from .types import GenerationConfig, SlideContent, ThemeId


THEME_STYLE_SNIPPETS = {
    "modern_newspaper": (
        "Swiss Style economic media editorial, monochrome cutout photography, "
        "white or cool gray background, jet black accents, asymmetric layout"
    ),
    "neo_retro_dev": (
        "neo-retro developer pixel-infographic style, off-white grid paper background, "
        "thick black borders, hot pink, bright yellow and cyan blocks, pixel icons"
    ),
    "anti_gravity": (
        "minimal airy tech aesthetic, pure white background, soft cyan-violet edge glows, floating cards"
    ),
}

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


def build_image_prompt(theme_id: ThemeId, base_prompt: str) -> str:
    style = THEME_STYLE_SNIPPETS.get(theme_id.value, "")
    return (
        f"{base_prompt}. Slide illustration in the style of: {style}. "
        "No text in the image, only illustration or photography."
    )


class ImageGenerator:
    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        output_dir: str = "output/assets/images",
    ):
        self.api_key = api_key
        self.model = model or os.environ.get("TOGETHER_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
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

    def generate_for_slides(self, config: GenerationConfig, slides: List[SlideContent]) -> List[SlideContent]:
        updated: List[SlideContent] = []
        for slide in slides:
            prompt = build_image_prompt(
                config.theme,
                slide.image_prompt or f"visual illustration for: {slide.title}",
            )
            slide.image_path = None
            try:
                payload: dict = {
                    "model": self.model,
                    "prompt": prompt,
                    "width": _fit_dim_to_model_constraints(config.video_size.width),
                    "height": _fit_dim_to_model_constraints(config.video_size.height),
                    "n": 1,
                }

                # Some models reject the `steps` parameter (handled by omitting it).
                if "FLUX.2" not in self.model:
                    payload["steps"] = 6

                headers = {"Authorization": f"Bearer {self.api_key}"}
                resp = requests.post(
                    "https://api.together.xyz/v1/images/generations",
                    headers=headers,
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                data0 = (data.get("data") or [{}])[0]

                filename = f"slide_{slide.index:02d}.png"
                out_path = os.path.join(self.output_dir, filename)

                if "url" in data0 and data0["url"]:
                    self._download_to_path(data0["url"], out_path)
                elif "b64_json" in data0 and data0["b64_json"]:
                    self._save_b64_to_path(data0["b64_json"], out_path)
                else:
                    raise RuntimeError(f"Unexpected Together images response shape: {data0.keys()}")

                slide.image_path = out_path
            except Exception as e:
                print(
                    f"[SudarVid] WARNING: Image generation failed for slide {slide.index}: {e}",
                    file=sys.stderr,
                )
            updated.append(slide)
        return updated

