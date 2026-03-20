from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import List, Optional

import jinja2
import yaml

# Load .env from project root when available (optional dependency: python-dotenv)
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

from .content_planner import ContentPlanner
from .image_gen import ImageGenerator
from .media import (
    build_full_video,
    concatenate_audio,
    compute_slide_durations,
    synthesize_all_slides,
    synthesize_deck_voiceover,
)
from .themes import get_theme
from .types import AnimationLevel, GenerationConfig, SlideContent, ThemeId, VideoSize


def load_config(path: str) -> GenerationConfig:
    if not path:
        raise ValueError("config_path is required when config_obj is not provided.")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return GenerationConfig(
        topic=data["topic"],
        audience=data.get("audience", "general audience"),
        language=data.get("language", "en"),
        theme=ThemeId(data["theme"]),
        slide_count=int(data.get("slide_count", 5)),
        video_size=VideoSize(**data["video_size"]),
        animation_level=AnimationLevel(data.get("animation_level", "subtle")),
        include_tts=bool(data.get("include_tts", True)),
        include_music=bool(data.get("include_music", True)),
        output_html=bool(data.get("output_html", True)),
        output_mp4=bool(data.get("output_mp4", False)),
        target_duration_seconds=data.get("target_duration_seconds"),
        custom_content=data.get("custom_content"),
    )


def _ensure_job_static(output_dir: str) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    static_src = repo_root / "static"
    if not static_src.exists():
        return
    static_dst = Path(output_dir) / "static"
    if static_dst.exists():
        return
    shutil.copytree(static_src, static_dst)


def render_html_deck(
    config: GenerationConfig,
    slides: List[SlideContent],
    output_dir: str,
    template_dir: Optional[str] = None,
) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    template_dir_path = Path(template_dir) if template_dir else (repo_root / "templates")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(template_dir_path)), autoescape=True)
    tpl = env.get_template("base.html.j2")

    _ensure_job_static(output_dir)

    if not slides:
        raise ValueError(
            "Cannot render slides.html: slide list is empty. "
            "This should not happen after planning; report a bug if you see it."
        )

    theme = get_theme(config.theme.value)
    html = tpl.render(
        language=config.language,
        width=config.video_size.width,
        height=config.video_size.height,
        theme_id=config.theme.value,
        theme=theme,
        animation_level=config.animation_level.value,
        include_tts=config.include_tts,
        output_mp4=config.output_mp4,
        slides=slides,
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "slides.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


def _relpath_posix(path: str, base_dir: str) -> str:
    return Path(path).resolve().relative_to(Path(base_dir).resolve()).as_posix()


def generate_video(
    config_path: Optional[str] = None,
    output_dir: str = "output",
    config_obj: Optional[GenerationConfig] = None,
) -> List[str]:
    config = config_obj if config_obj is not None else load_config(config_path or "")

    together_api_key = os.environ.get("TOGETHER_API_KEY")
    if not together_api_key:
        raise RuntimeError("TOGETHER_API_KEY is not set")

    os.makedirs(output_dir, exist_ok=True)

    planner = ContentPlanner(api_key=together_api_key)
    slides = planner.plan_slides(config)

    images_dir = os.path.join(output_dir, "assets", "images")
    image_gen = ImageGenerator(api_key=together_api_key, output_dir=images_dir)
    slides = image_gen.generate_for_slides(config, slides)

    for s in slides:
        if s.image_path:
            s.image_path = _relpath_posix(s.image_path, output_dir)

    # For an HTML preview with synchronized audio, we need the voiceover + slide durations
    # before rendering `slides.html`. This also allows HTML-only runs when ffmpeg/ffprobe
    # are missing (duration estimation uses a fallback when ffprobe fails).
    if config.output_html and config.include_tts:
        audio_dir = os.path.join(output_dir, "audio")
        per_slide_tts = asyncio.run(synthesize_all_slides(slides, audio_dir, config.language))
        voiceover_path = os.path.join(audio_dir, "voiceover.mp3")
        ffmpeg_exists = bool(shutil.which("ffmpeg"))
        # Empty per-slide list (shouldn't happen if slides exist) would make ffmpeg concat fail.
        if ffmpeg_exists and per_slide_tts:
            concatenate_audio(per_slide_tts, voiceover_path)
        else:
            # HTML-only preview: create a single voiceover file without ffmpeg.
            asyncio.run(synthesize_deck_voiceover(slides, voiceover_path, config.language))
        compute_slide_durations(slides, per_slide_tts_paths=per_slide_tts, padding_seconds=1.2)

    output_files: List[str] = []

    html_path: Optional[str] = None
    if config.output_html:
        html_path = render_html_deck(config, slides, output_dir=output_dir)
        output_files.append(html_path)

    if config.output_mp4:
        if not html_path:
            html_path = render_html_deck(config, slides, output_dir=output_dir)
            output_files.append(html_path)
        mp4_path = build_full_video(config, slides, html_path=html_path, output_dir=output_dir)
        output_files.append(mp4_path)

    return output_files

