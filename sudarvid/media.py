from __future__ import annotations

import asyncio
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import edge_tts

from .types import GenerationConfig, SlideContent

REPO_ROOT = Path(__file__).resolve().parents[1]

VOICE_MAP = {
    "en": "en-US-AriaNeural",
    "en-us": "en-US-AriaNeural",
    "en-male": "en-US-GuyNeural",
    "en-uk": "en-GB-SoniaNeural",
    "en-uk-male": "en-GB-RyanNeural",
    "en-au": "en-AU-NatashaNeural",
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "pt": "pt-BR-FranciscaNeural",
    "hi": "hi-IN-SwaraNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-ShrutiNeural",
    "ml": "ml-IN-SobhanaNeural",
    "bn": "bn-IN-TanishaaNeural",
}

# Bundled background loops (static/music/). See static/music/README.md — WAV sources, ffmpeg muxes to MP3.
THEME_MUSIC_MAP = {
    "sports": "music/loop_energetic.wav",
    "classic_pop": "music/loop_energetic.wav",
    "digital_neo_pop": "music/loop_energetic.wav",
    "pink_street": "music/loop_energetic.wav",
    "neo_retro_dev": "music/loop_retro.wav",
    "tech_neon": "music/loop_retro.wav",
    "seminar_minimal": "music/loop_ambient.wav",
    "anti_gravity": "music/loop_ambient.wav",
    "sharp_minimalism": "music/loop_ambient.wav",
    "studio_premium": "music/loop_ambient.wav",
    "magazine": "music/loop_soft.wav",
    "royal_blue_red": "music/loop_soft.wav",
    "manga": "music/loop_soft.wav",
    "modern_newspaper": "music/loop_soft.wav",
    "yellow_black": "music/loop_energetic.wav",
    "black_orange": "music/loop_energetic.wav",
    "mincho_handwritten": "music/loop_soft.wav",
    "deformed_persona": "music/loop_soft.wav",
}


def resolve_voice(language: str, voice_override: Optional[str] = None) -> str:
    if voice_override and str(voice_override).strip():
        return str(voice_override).strip()
    return VOICE_MAP.get(language.lower(), "en-US-AriaNeural")


def bundled_music_source_path(theme_id: str) -> Optional[str]:
    """Absolute path to a bundled MP3 under static/music/, or None if missing."""
    rel = THEME_MUSIC_MAP.get(theme_id, "music/loop_ambient.wav")
    p = REPO_ROOT / "static" / rel
    return str(p) if p.is_file() else None


async def _synthesize_slide(text: str, output_path: str, voice: str) -> None:
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(output_path)


async def synthesize_all_slides(
    slides: List[SlideContent],
    audio_dir: str,
    language: str,
    voice_override: Optional[str] = None,
) -> List[str]:
    os.makedirs(audio_dir, exist_ok=True)
    voice = resolve_voice(language, voice_override)
    tasks = []
    paths: List[str] = []
    for slide in slides:
        p = os.path.join(audio_dir, f"slide_{slide.index:02d}_tts.mp3")
        paths.append(p)
        tasks.append(_synthesize_slide(slide.narration or slide.title, p, voice))
    await asyncio.gather(*tasks)
    return paths


async def synthesize_deck_voiceover(
    slides: List[SlideContent],
    output_path: str,
    language: str,
    voice_override: Optional[str] = None,
) -> None:
    """
    Synthesize one combined voiceover file without using ffmpeg concatenation.
    This is used for HTML-only preview when ffmpeg/ffprobe are missing.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    voice = resolve_voice(language, voice_override)
    parts: List[str] = []
    for slide in slides:
        t = slide.narration or slide.title
        if t:
            parts.append(t)
    text = "\n".join(parts).strip()
    if not text:
        text = " "

    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(output_path)


def get_audio_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def _create_silence(output_path: str, duration_ms: int) -> None:
    if os.path.exists(output_path):
        return
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            str(duration_ms / 1000),
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            output_path,
        ],
        check=True,
        capture_output=True,
    )


def concatenate_audio(per_slide_paths: List[str], output_path: str, silence_between_ms: int = 400) -> str:
    if not per_slide_paths:
        raise ValueError("No per-slide audio paths provided.")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    silence_path = os.path.join(os.path.dirname(output_path), "_silence.mp3")
    _create_silence(silence_path, duration_ms=silence_between_ms)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_file = f.name
        for p in per_slide_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
            f.write(f"file '{os.path.abspath(silence_path)}'\n")

    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path],
        check=True,
        capture_output=True,
    )
    os.unlink(concat_file)
    return output_path


def compute_slide_durations(
    slides: List[SlideContent],
    per_slide_tts_paths: Optional[List[str]] = None,
    padding_seconds: float = 1.2,
) -> List[SlideContent]:
    def estimate_duration_seconds(text: str) -> float:
        # Simple speech-rate heuristic: words per minute -> seconds per word.
        words = re.findall(r"[A-Za-z0-9']+", text or "")
        word_count = max(1, len(words))
        wpm = 170.0
        seconds = word_count * (60.0 / wpm)
        seconds += 0.5
        return max(3.0, min(seconds, 30.0))

    for i, slide in enumerate(slides):
        if per_slide_tts_paths and i < len(per_slide_tts_paths):
            p = per_slide_tts_paths[i]
            if os.path.exists(p):
                try:
                    slide.duration_seconds = get_audio_duration(p) + padding_seconds
                    continue
                except Exception:
                    # If ffprobe is missing/unavailable, fall back to a text-based estimate.
                    # This keeps HTML preview generation working even without ffmpeg tooling.
                    source_text = slide.narration or slide.title
                    slide.duration_seconds = estimate_duration_seconds(source_text) + padding_seconds
                    continue
        slide.duration_seconds = 6.0
    return slides


def capture_slide_frames(
    html_path: str,
    slides: List[SlideContent],
    frames_dir: str,
    width: int,
    height: int,
    animation_settle_ms: int = 900,
) -> List[Tuple[str, float]]:
    # Future improvement:
    # Switch from screenshot-based sampling to Playwright video recording for
    # smoother animations (no need to tune sample fps / frame caps). The rest
    # of the pipeline can stay the same: capture visuals, then mux in
    # voiceover/music via ffmpeg.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError("playwright is not installed. Run: pip install playwright && playwright install chromium") from e

    os.makedirs(frames_dir, exist_ok=True)
    abs_html = Path(html_path).resolve().as_uri()
    out: List[Tuple[str, float]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.add_init_script("window.IS_CAPTURE = true;")
        page.goto(abs_html, wait_until="networkidle")
        page.wait_for_timeout(800)

        # "Low" smoothness defaults: capture a small number of frames per slide.
        target_sample_fps = 6.0
        max_frames_per_slide = 8

        for slide in slides:
            page.evaluate(f"window.SudarVid && window.SudarVid.showSlide({slide.index})")
            settle_seconds = animation_settle_ms / 1000.0
            remaining_seconds = max(slide.duration_seconds - settle_seconds, 0.0)
            desired_frames = int(math.ceil(slide.duration_seconds * target_sample_fps))
            frames_per_slide = max(1, min(desired_frames, max_frames_per_slide))
            duration_per_frame = slide.duration_seconds / frames_per_slide

            # First frame: after the animation settles.
            page.wait_for_timeout(animation_settle_ms)

            # Subsequent frames: evenly sample the rest of the slide time.
            interval_ms: int = 0
            if frames_per_slide > 1:
                interval_seconds = remaining_seconds / (frames_per_slide - 1)
                interval_ms = int(round(interval_seconds * 1000.0))

            for frame_idx in range(frames_per_slide):
                if frame_idx > 0:
                    page.wait_for_timeout(interval_ms)

                frame_path = os.path.join(
                    frames_dir,
                    f"frame_{slide.index:04d}_{frame_idx:02d}.png",
                )
                page.screenshot(
                    path=frame_path,
                    clip={"x": 0, "y": 0, "width": width, "height": height},
                )
                out.append((frame_path, duration_per_frame))

        browser.close()

    return out


def build_video_from_frames(
    frame_infos: List[Tuple[str, float]],
    voiceover_path: Optional[str],
    music_path: Optional[str],
    output_path: str,
    width: int,
    height: int,
    fps: int = 30,
    music_volume: float = 0.18,
    voice_volume: float = 1.0,
) -> str:
    if not frame_infos:
        raise ValueError("No frames provided.")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_file = f.name
        for frame_path, duration_seconds in frame_infos:
            f.write(f"file '{os.path.abspath(frame_path)}'\n")
            f.write(f"duration {duration_seconds:.3f}\n")
        f.write(f"file '{os.path.abspath(frame_infos[-1][0])}'\n")

    cmd: List[str] = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file]

    audio_inputs = 0
    if voiceover_path and os.path.exists(voiceover_path):
        cmd += ["-i", voiceover_path]
        audio_inputs += 1
    if music_path and os.path.exists(music_path):
        cmd += ["-i", music_path]
        audio_inputs += 1

    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    cmd += ["-vf", vf]

    if audio_inputs == 2:
        cmd += [
            "-filter_complex",
            f"[1:a]volume={voice_volume}[a1];[2:a]volume={music_volume}[a2];[a1][a2]amix=inputs=2:normalize=0[aout]",
            "-map",
            "0:v",
            "-map",
            "[aout]",
        ]
    elif audio_inputs == 1:
        cmd += ["-map", "0:v", "-map", "1:a"]
    else:
        cmd += ["-map", "0:v"]

    cmd += [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-movflags",
        "+faststart",
        "-shortest",
        output_path,
    ]

    subprocess.run(cmd, check=True)
    os.unlink(concat_file)
    return output_path


def build_full_video(
    config: GenerationConfig,
    slides: List[SlideContent],
    html_path: str,
    output_dir: str,
    custom_music_path: Optional[str] = None,
    existing_voiceover_path: Optional[str] = None,
    existing_per_slide_tts: Optional[List[str]] = None,
) -> str:
    audio_dir = os.path.join(output_dir, "audio")
    frames_dir = os.path.join(output_dir, "frames")
    video_dir = os.path.join(output_dir, "video")
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(video_dir, exist_ok=True)

    voiceover_path: Optional[str] = None
    per_slide_tts: Optional[List[str]] = None
    music_path: Optional[str] = None

    if config.include_tts:
        reuse = (
            existing_voiceover_path
            and existing_per_slide_tts
            and os.path.isfile(existing_voiceover_path)
            and len(existing_per_slide_tts) == len(slides)
            and all(os.path.isfile(p) for p in existing_per_slide_tts)
        )
        if reuse:
            voiceover_path = existing_voiceover_path
            per_slide_tts = existing_per_slide_tts
        else:
            per_slide_tts = asyncio.run(
                synthesize_all_slides(slides, audio_dir, config.language, config.voice_override)
            )
            voiceover_path = os.path.join(audio_dir, "voiceover.mp3")
            concatenate_audio(per_slide_tts, voiceover_path)

    slides = compute_slide_durations(slides, per_slide_tts_paths=per_slide_tts, padding_seconds=1.2)
    total_duration = sum(s.duration_seconds for s in slides)

    music_src = custom_music_path
    if config.include_music and not music_src:
        music_src = bundled_music_source_path(config.theme.value)

    if config.include_music and music_src and os.path.isfile(music_src):
        music_path = os.path.join(audio_dir, "music.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-i", music_src, "-t", str(total_duration + 2.0), music_path],
            check=True,
        )

    frame_paths = capture_slide_frames(
        html_path=html_path,
        slides=slides,
        frames_dir=frames_dir,
        width=config.video_size.width,
        height=config.video_size.height,
    )

    output_path = os.path.join(video_dir, "output.mp4")
    return build_video_from_frames(
        frame_infos=frame_paths,
        voiceover_path=voiceover_path,
        music_path=music_path,
        output_path=output_path,
        width=config.video_size.width,
        height=config.video_size.height,
    )

