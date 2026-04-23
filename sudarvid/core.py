from __future__ import annotations

import asyncio
import json
import os
import random
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
        learning_objectives=data.get("learning_objectives"),
        difficulty=data.get("difficulty"),
        source_notes=data.get("source_notes"),
        constraints=data.get("constraints"),
        persona=data.get("persona"),
        voice_override=data.get("voice_override"),
        image_model=data.get("image_model"),
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


def write_slides_manifest(output_dir: str, slides: List[SlideContent]) -> str:
    """JSON summary for API/clients: layout and visual_template per slide."""
    path = os.path.join(output_dir, "slides_manifest.json")
    payload = [
        {
            "index": s.index,
            "title": s.title,
            "narration": s.narration,
            "layout_kind": s.layout_kind,
            "visual_template": getattr(s, "visual_template", "full_bleed_bg"),
            "duration_seconds": s.duration_seconds,
        }
        for s in slides
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def _relpath_posix(path: str, base_dir: str) -> str:
    return Path(path).resolve().relative_to(Path(base_dir).resolve()).as_posix()


def _inject_bookend_slides(config: GenerationConfig, slides: List[SlideContent]) -> List[SlideContent]:
    """Prepend intro and append branded outro slides (fixed short durations, no images)."""
    if not slides:
        return slides
    topic = (config.topic or "Presentation").strip() or "Presentation"
    intro = SlideContent(
        index=0,
        title=f"Welcome to {topic[:170]}",
        bullets=[],
        narration=f"Welcome to Sudar. In this course, we will learn about {topic}. Let's begin.",
        image_prompt="",
        image_path=None,
        duration_seconds=2.8,
        layout_kind="intro",
        visual_template="none",
        subtitle="Powered by SudarVid",
    )
    shifted: List[SlideContent] = []
    for j, s in enumerate(slides):
        shifted.append(replace(s, index=j + 1))
    outro = SlideContent(
        index=len(shifted) + 1,
        title="Sudar",
        bullets=[],
        narration="Thanks for learning with Sudar.",
        image_prompt="",
        image_path=None,
        duration_seconds=2.6,
        layout_kind="outro",
        visual_template="none",
        subtitle=None,
    )
    return [intro] + shifted + [outro]


def _inject_quiz_checkpoints(slides: List[SlideContent]) -> List[SlideContent]:
    """Insert quiz slides from config (if present), else auto-generate checkpoints."""
    if len(slides) < 2:
        return slides

    cadence = max(2, int(os.getenv("SUDARVID_QUIZ_CADENCE", "2")))
    output: List[SlideContent] = []
    for s in slides:
        output.append(s)
        if s.index > 0 and s.index % cadence == 0 and s.bullets:
            options = [b.strip() for b in s.bullets if (b or "").strip()]
            if len(options) < 2:
                continue
            options = options[:4]
            rng = random.Random(f"{s.title}|{s.index}|{len(options)}")
            correct_answer = options[0]
            rng.shuffle(options)
            correct_index = options.index(correct_answer)
            quiz_slide = SlideContent(
                index=0,  # reindexed below
                title="Quick Checkpoint",
                bullets=options,
                narration="",
                image_prompt="",
                image_path=None,
                duration_seconds=8.0,
                layout_kind="quiz",
                visual_template="none",
                subtitle=f"Which option best matches: {s.title}",
            )
            setattr(quiz_slide, "quiz_correct_index", correct_index)
            setattr(
                quiz_slide,
                "quiz_explanation",
                f"The best answer is: {correct_answer}",
            )
            output.append(quiz_slide)

    reindexed: List[SlideContent] = []
    for idx, slide in enumerate(output):
        reindexed.append(replace(slide, index=idx))
    return reindexed


def _iter_quiz_dicts(payload: Any) -> List[Dict[str, Any]]:
    """Recursively collect quiz-like dictionaries from arbitrary payloads."""
    if payload is None:
        return []
    if isinstance(payload, dict):
        out: List[Dict[str, Any]] = []
        if any(k in payload for k in ("question", "options", "choices", "answers", "correct")):
            out.append(payload)
        for key in ("quiz", "quizzes", "questions", "module_quiz", "moduleQuiz", "quiz_questions"):
            if key in payload:
                out.extend(_iter_quiz_dicts(payload.get(key)))
        for value in payload.values():
            if isinstance(value, (dict, list)):
                out.extend(_iter_quiz_dicts(value))
        return out
    if isinstance(payload, list):
        out = []
        for item in payload:
            out.extend(_iter_quiz_dicts(item))
        return out
    return []


def _extract_module_quiz_items(config: GenerationConfig) -> List[Dict[str, Any]]:
    """Read module quiz JSON when available in custom_content/source_notes."""
    candidates: List[Any] = [getattr(config, "custom_content", None), getattr(config, "source_notes", None)]
    items: List[Dict[str, Any]] = []
    for payload in candidates:
        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
            except Exception:
                parsed = None
            if parsed is not None:
                items.extend(_iter_quiz_dicts(parsed))
        elif isinstance(payload, (dict, list)):
            items.extend(_iter_quiz_dicts(payload))
    return items


def _build_quiz_slide_from_item(item: Dict[str, Any], idx_seed: int) -> Optional[SlideContent]:
    q = str(item.get("question") or item.get("prompt") or "").strip()
    if not q:
        return None

    raw_options = (
        item.get("options")
        or item.get("choices")
        or item.get("answers")
        or item.get("answer_options")
        or []
    )
    options: List[str] = []
    if isinstance(raw_options, list):
        for opt in raw_options:
            if isinstance(opt, dict):
                text = str(opt.get("text") or opt.get("label") or "").strip()
            else:
                text = str(opt).strip()
            if text:
                options.append(text)
    if len(options) < 2:
        return None
    options = options[:4]

    correct_raw = item.get("correct") or item.get("correct_answer") or item.get("answer")
    if isinstance(correct_raw, int):
        correct_idx_orig = max(0, min(len(options) - 1, int(correct_raw)))
        correct_answer = options[correct_idx_orig]
    else:
        correct_answer = str(correct_raw or options[0]).strip()
        if correct_answer not in options:
            correct_answer = options[0]

    rng = random.Random(f"{q}|{idx_seed}|{len(options)}")
    rng.shuffle(options)
    correct_idx = options.index(correct_answer)
    explanation = str(item.get("explanation") or item.get("reason") or f"The best answer is: {correct_answer}").strip()

    slide = SlideContent(
        index=0,
        title="Quick Checkpoint",
        bullets=options,
        narration="",
        image_prompt="",
        image_path=None,
        duration_seconds=10.0,
        layout_kind="quiz",
        visual_template="none",
        subtitle=q,
    )
    setattr(slide, "quiz_correct_index", correct_idx)
    setattr(slide, "quiz_explanation", explanation)
    return slide


def _inject_module_quiz_slides(config: GenerationConfig, slides: List[SlideContent]) -> List[SlideContent]:
    quiz_items = _extract_module_quiz_items(config)
    if not quiz_items:
        return _inject_quiz_checkpoints(slides)

    cadence = max(2, int(os.getenv("SUDARVID_QUIZ_CADENCE", "2")))
    quiz_slides: List[SlideContent] = []
    for i, item in enumerate(quiz_items):
        q_slide = _build_quiz_slide_from_item(item, idx_seed=i)
        if q_slide is not None:
            quiz_slides.append(q_slide)
    if not quiz_slides:
        return _inject_quiz_checkpoints(slides)

    output: List[SlideContent] = []
    q_idx = 0
    for s in slides:
        output.append(s)
        if s.index > 0 and s.index % cadence == 0 and q_idx < len(quiz_slides):
            output.append(quiz_slides[q_idx])
            q_idx += 1

    reindexed: List[SlideContent] = []
    for idx, slide in enumerate(output):
        reindexed.append(replace(slide, index=idx))
    return reindexed


def _apply_target_duration_seconds(slides: List[SlideContent], target: float) -> None:
    """Scale per-slide durations toward a target total (after measured/estimated durations exist)."""
    actual = sum(s.duration_seconds for s in slides)
    scale = float(target) / max(actual, 1.0)
    if 0.5 < scale < 2.0:
        for s in slides:
            s.duration_seconds = max(3.0, s.duration_seconds * scale)


def generate_video(
    config_path: Optional[str] = None,
    output_dir: str = "output",
    config_obj: Optional[GenerationConfig] = None,
    progress_callback: Optional[Callable[[str, dict], None]] = None,
) -> List[str]:
    config = config_obj if config_obj is not None else load_config(config_path or "")
    report = progress_callback or (lambda *_args, **_kwargs: None)

    together_api_key = os.environ.get("TOGETHER_API_KEY")
    if not together_api_key:
        raise RuntimeError("TOGETHER_API_KEY is not set")

    os.makedirs(output_dir, exist_ok=True)

    planner = ContentPlanner(api_key=together_api_key)
    report("planning", {"message": "Planning slides"})
    slides = planner.plan_slides(config)
    slides = _inject_module_quiz_slides(config, slides)
    slides = _inject_bookend_slides(config, slides)

    images_dir = os.path.join(output_dir, "assets", "images")
    image_gen = ImageGenerator(api_key=together_api_key, model=config.image_model, output_dir=images_dir)
    report("images_start", {"message": "Generating images", "total": len(slides)})
    slides = image_gen.generate_for_slides(
        config,
        slides,
        progress_callback=lambda current, total: report(
            "image_progress",
            {"current": current, "total": total, "message": f"image_{current}_of_{total}"},
        ),
    )

    for s in slides:
        if s.image_path:
            s.image_path = _relpath_posix(s.image_path, output_dir)

    voiceover_path: Optional[str] = None
    per_slide_tts: Optional[List[str]] = None

    # Voiceover + per-slide durations before rendering HTML or encoding MP4.
    if config.include_tts and (config.output_html or config.output_mp4):
        report("audio", {"message": "Generating voiceover"})
        audio_dir = os.path.join(output_dir, "audio")
        per_slide_tts = asyncio.run(
            synthesize_all_slides(slides, audio_dir, config.language, config.voice_override)
        )
        voiceover_path = os.path.join(audio_dir, "voiceover.mp3")
        ffmpeg_exists = bool(shutil.which("ffmpeg"))
        if ffmpeg_exists and per_slide_tts:
            concatenate_audio(per_slide_tts, voiceover_path)
        else:
            asyncio.run(
                synthesize_deck_voiceover(slides, voiceover_path, config.language, config.voice_override)
            )
        compute_slide_durations(slides, per_slide_tts_paths=per_slide_tts)

    # Scaling slide times breaks sync with the pre-rendered voiceover MP3; skip when TTS is on.
    if config.target_duration_seconds is not None and not (
        config.include_tts and per_slide_tts
    ):
        _apply_target_duration_seconds(slides, float(config.target_duration_seconds))

    output_files: List[str] = []

    html_path: Optional[str] = None
    if config.output_html:
        report("rendering", {"message": "Rendering HTML deck"})
        html_path = render_html_deck(config, slides, output_dir=output_dir)
        output_files.append(html_path)
        manifest_path = write_slides_manifest(output_dir, slides)
        output_files.append(manifest_path)

    if config.output_mp4:
        if not html_path:
            report("rendering", {"message": "Rendering HTML deck"})
            html_path = render_html_deck(config, slides, output_dir=output_dir)
            output_files.append(html_path)
            manifest_path = write_slides_manifest(output_dir, slides)
            output_files.append(manifest_path)
        report("rendering_video", {"message": "Rendering MP4"})
        try:
            mp4_path = build_full_video(
                config,
                slides,
                html_path=html_path,
                output_dir=output_dir,
                existing_voiceover_path=voiceover_path,
                existing_per_slide_tts=per_slide_tts,
            )
            output_files.append(mp4_path)
        except Exception as e:
            # Slides, images, and narration are already on disk; MP4 is best-effort.
            print(f"[SudarVid] MP4 encoding failed (slide deck is still available): {e}")
            report(
                "video_failed",
                {"message": str(e), "nonfatal": True},
            )

    return output_files

