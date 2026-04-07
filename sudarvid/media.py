from __future__ import annotations

import asyncio
import json
import math
import os
import random
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import edge_tts
from edge_tts.exceptions import NoAudioReceived, UnexpectedResponse, WebSocketError

from .types import GenerationConfig, SlideContent

REPO_ROOT = Path(__file__).resolve().parents[1]

# #region agent log
_AGENT_DEBUG_LOG = REPO_ROOT / "debug-7b3129.log"


def _agent_debug(
    location: str,
    message: str,
    hypothesis_id: str,
    data: dict,
    run_id: str = "pre-fix",
) -> None:
    try:
        payload = {
            "sessionId": "7b3129",
            "id": f"log_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
            "timestamp": int(time.time() * 1000),
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
        }
        with open(_AGENT_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


# #endregion

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

# Keep in sync with silence inserted between per-slide clips in concatenate_audio.
TTS_SILENCE_BETWEEN_MS = 400

# Short line for voice preview samples (Edge-tts).
_TTS_PREVIEW_LINE = "Hello — this is a quick SudarVid voice preview."

# Curated Edge voices for the UI (id must be valid for edge-tts).
CURATED_TTS_VOICES: List[dict] = [
    {"id": "en-US-AriaNeural", "label": "English (US) — Aria", "locale": "en-US"},
    {"id": "en-US-JennyNeural", "label": "English (US) — Jenny", "locale": "en-US"},
    {"id": "en-US-GuyNeural", "label": "English (US) — Guy", "locale": "en-US"},
    {"id": "en-US-EricNeural", "label": "English (US) — Eric", "locale": "en-US"},
    {"id": "en-US-DavisNeural", "label": "English (US) — Davis", "locale": "en-US"},
    {"id": "en-US-JaneNeural", "label": "English (US) — Jane", "locale": "en-US"},
    {"id": "en-US-JasonNeural", "label": "English (US) — Jason", "locale": "en-US"},
    {"id": "en-US-NancyNeural", "label": "English (US) — Nancy", "locale": "en-US"},
    {"id": "en-US-TonyNeural", "label": "English (US) — Tony", "locale": "en-US"},
    {"id": "en-GB-SoniaNeural", "label": "English (UK) — Sonia", "locale": "en-GB"},
    {"id": "en-GB-RyanNeural", "label": "English (UK) — Ryan", "locale": "en-GB"},
    {"id": "en-GB-LibbyNeural", "label": "English (UK) — Libby", "locale": "en-GB"},
    {"id": "en-GB-MaisieNeural", "label": "English (UK) — Maisie", "locale": "en-GB"},
    {"id": "en-AU-NatashaNeural", "label": "English (AU) — Natasha", "locale": "en-AU"},
    {"id": "en-AU-WilliamNeural", "label": "English (AU) — William", "locale": "en-AU"},
    {"id": "en-IN-NeerjaNeural", "label": "English (IN) — Neerja", "locale": "en-IN"},
    {"id": "en-IN-PrabhatNeural", "label": "English (IN) — Prabhat", "locale": "en-IN"},
    {"id": "de-DE-KatjaNeural", "label": "German — Katja", "locale": "de-DE"},
    {"id": "de-DE-ConradNeural", "label": "German — Conrad", "locale": "de-DE"},
    {"id": "de-DE-AmalaNeural", "label": "German — Amala", "locale": "de-DE"},
    {"id": "fr-FR-DeniseNeural", "label": "French — Denise", "locale": "fr-FR"},
    {"id": "fr-FR-HenriNeural", "label": "French — Henri", "locale": "fr-FR"},
    {"id": "es-ES-ElviraNeural", "label": "Spanish — Elvira", "locale": "es-ES"},
    {"id": "es-ES-AlvaroNeural", "label": "Spanish — Alvaro", "locale": "es-ES"},
    {"id": "es-MX-DaliaNeural", "label": "Spanish (MX) — Dalia", "locale": "es-MX"},
    {"id": "es-MX-JorgeNeural", "label": "Spanish (MX) — Jorge", "locale": "es-MX"},
    {"id": "pt-BR-FranciscaNeural", "label": "Portuguese (BR) — Francisca", "locale": "pt-BR"},
    {"id": "pt-BR-AntonioNeural", "label": "Portuguese (BR) — Antonio", "locale": "pt-BR"},
    {"id": "it-IT-ElsaNeural", "label": "Italian — Elsa", "locale": "it-IT"},
    {"id": "it-IT-DiegoNeural", "label": "Italian — Diego", "locale": "it-IT"},
    {"id": "ja-JP-NanamiNeural", "label": "Japanese — Nanami", "locale": "ja-JP"},
    {"id": "ja-JP-KeitaNeural", "label": "Japanese — Keita", "locale": "ja-JP"},
    {"id": "zh-CN-XiaoxiaoNeural", "label": "Chinese — Xiaoxiao", "locale": "zh-CN"},
    {"id": "zh-CN-YunxiNeural", "label": "Chinese — Yunxi", "locale": "zh-CN"},
    {"id": "ko-KR-SunHiNeural", "label": "Korean — SunHi", "locale": "ko-KR"},
    {"id": "ko-KR-InJoonNeural", "label": "Korean — InJoon", "locale": "ko-KR"},
    {"id": "hi-IN-SwaraNeural", "label": "Hindi — Swara", "locale": "hi-IN"},
    {"id": "hi-IN-MadhurNeural", "label": "Hindi — Madhur", "locale": "hi-IN"},
    {"id": "ta-IN-PallaviNeural", "label": "Tamil — Pallavi", "locale": "ta-IN"},
    {"id": "ta-IN-ValluvarNeural", "label": "Tamil — Valluvar", "locale": "ta-IN"},
    {"id": "te-IN-ShrutiNeural", "label": "Telugu — Shruti", "locale": "te-IN"},
    {"id": "te-IN-MohanNeural", "label": "Telugu — Mohan", "locale": "te-IN"},
    {"id": "ml-IN-SobhanaNeural", "label": "Malayalam — Sobhana", "locale": "ml-IN"},
    {"id": "ml-IN-MidhunNeural", "label": "Malayalam — Midhun", "locale": "ml-IN"},
    {"id": "bn-IN-TanishaaNeural", "label": "Bengali — Tanishaa", "locale": "bn-IN"},
    {"id": "bn-IN-BashkarNeural", "label": "Bengali — Bashkar", "locale": "bn-IN"},
    {"id": "ar-SA-ZariyahNeural", "label": "Arabic — Zariyah", "locale": "ar-SA"},
    {"id": "ar-SA-HamedNeural", "label": "Arabic — Hamed", "locale": "ar-SA"},
    {"id": "nl-NL-FennaNeural", "label": "Dutch — Fenna", "locale": "nl-NL"},
    {"id": "nl-NL-MaartenNeural", "label": "Dutch — Maarten", "locale": "nl-NL"},
    {"id": "pl-PL-AgnieszkaNeural", "label": "Polish — Agnieszka", "locale": "pl-PL"},
    {"id": "pl-PL-MarekNeural", "label": "Polish — Marek", "locale": "pl-PL"},
    {"id": "ru-RU-SvetlanaNeural", "label": "Russian — Svetlana", "locale": "ru-RU"},
    {"id": "ru-RU-DmitryNeural", "label": "Russian — Dmitry", "locale": "ru-RU"},
    {"id": "tr-TR-EmelNeural", "label": "Turkish — Emel", "locale": "tr-TR"},
    {"id": "tr-TR-AhmetNeural", "label": "Turkish — Ahmet", "locale": "tr-TR"},
]


def language_presets() -> List[dict]:
    labels = {
        "en": "English (default US)",
        "en-us": "English (US)",
        "en-male": "English (male preset)",
        "en-uk": "English (UK)",
        "en-uk-male": "English (UK male)",
        "en-au": "English (Australia)",
        "ja": "Japanese",
        "zh": "Chinese (Mandarin)",
        "ko": "Korean",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "pt": "Portuguese (Brazil)",
        "hi": "Hindi",
        "ta": "Tamil",
        "te": "Telugu",
        "ml": "Malayalam",
        "bn": "Bengali",
    }
    out: List[dict] = []
    for key in sorted(VOICE_MAP.keys(), key=lambda k: (labels.get(k, k), k)):
        out.append({"id": key, "label": labels.get(key, key), "default_voice": VOICE_MAP[key]})
    return out


_ALLOWED_VOICE_IDS = {v["id"] for v in CURATED_TTS_VOICES} | set(VOICE_MAP.values())


def is_allowed_tts_voice(voice: str) -> bool:
    v = (voice or "").strip()
    if v in _ALLOWED_VOICE_IDS:
        return True
    # Allow any standard Edge neural id for power users.
    if re.fullmatch(r"[a-z]{2}-[A-Z]{2}-[A-Za-z0-9]+Neural", v):
        return True
    return False


def preview_audio_cache_path(voice: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", voice.strip())
    return REPO_ROOT / ".cache" / "tts_preview" / f"{safe}.mp3"


async def synthesize_tts_preview_file(voice: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(_TTS_PREVIEW_LINE, voice=voice.strip())
    await communicate.save(str(output_path))

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


# Microsoft Edge TTS often returns no audio when too many WebSocket sessions run at once.
_TTS_MAX_CONCURRENT = 3
_TTS_MAX_ATTEMPTS = 5
_TTS_RETRY_EXCEPTIONS = (NoAudioReceived, WebSocketError, UnexpectedResponse)


def _normalize_tts_text(text: str) -> str:
    """
    Edge TTS returns NoAudioReceived for some minimal inputs (e.g. a lone '.').
    Require at least one alphanumeric character so synthesis always receives valid speech.
    """
    t = (text or "").strip() or " "
    if any(ch.isalnum() for ch in t):
        return t
    return "This slide has no spoken narration."


async def _synthesize_slide(text: str, output_path: str, voice: str) -> None:
    """Call edge-tts with retries; empty narration becomes a minimal utterance."""
    t = _normalize_tts_text(text)
    last_err: Optional[Exception] = None
    for attempt in range(_TTS_MAX_ATTEMPTS):
        try:
            communicate = edge_tts.Communicate(t, voice=voice)
            await communicate.save(output_path)
            return
        except _TTS_RETRY_EXCEPTIONS as e:
            last_err = e
            if attempt >= _TTS_MAX_ATTEMPTS - 1:
                break
            delay = 0.75 * (2**attempt) + random.uniform(0, 0.35)
            await asyncio.sleep(delay)
    assert last_err is not None
    # #region agent log
    _agent_debug(
        "media.py:_synthesize_slide",
        "edge-tts failed after retries",
        "H2",
        {
            "voice": voice,
            "exc_type": type(last_err).__name__,
            "exc_str": str(last_err)[:400],
            "text_len": len(t),
            "last_attempt_index": attempt,
        },
    )
    # #endregion
    raise last_err


def _normalize_caption_word(w: str) -> str:
    return re.sub(r"^[^\w']+|[^\w']+$", "", (w or "").strip()).lower()


async def _synthesize_slide_with_word_times(
    text: str, output_path: str, voice: str
) -> tuple[list[str], list[int]]:
    """
    Stream edge-tts audio to disk and capture word-boundary timestamps.
    Returns (words, times_ms), both aligned by index.
    """
    t = _normalize_tts_text(text)
    # IMPORTANT: boundary defaults to SentenceBoundary; request WordBoundary for word-level timestamps.
    communicate = edge_tts.Communicate(t, voice=voice, boundary="WordBoundary")
    words: list[str] = []
    times_ms: list[int] = []

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    # edge-tts yields events: audio bytes + word boundary metadata
    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if not isinstance(chunk, dict):
                continue
            ctype = chunk.get("type") or chunk.get("Type") or ""
            if ctype == "audio":
                data = chunk.get("data") or chunk.get("Data")
                if isinstance(data, (bytes, bytearray)):
                    f.write(data)
            elif ctype in ("WordBoundary", "wordBoundary", "word_boundary"):
                # edge-tts commonly provides: offset (100ns units), duration, text, and/or text offset/length
                off = chunk.get("offset") or chunk.get("Offset") or 0
                try:
                    off_ms = int(round(float(off) / 10000.0))
                except Exception:
                    off_ms = 0

                w = chunk.get("text") or chunk.get("Text")
                if not isinstance(w, str) or not w.strip():
                    # Try substring extraction if the API gives character offsets
                    toff = chunk.get("text_offset") or chunk.get("textOffset") or chunk.get("TextOffset")
                    tlen = chunk.get("text_length") or chunk.get("textLength") or chunk.get("TextLength")
                    if isinstance(toff, int) and isinstance(tlen, int) and tlen > 0:
                        w = t[toff : toff + tlen]
                if isinstance(w, str) and w.strip():
                    words.append(w.strip())
                    times_ms.append(max(0, off_ms))

    # Filter out empty / punctuation-only tokens; keep times aligned
    filtered_words: list[str] = []
    filtered_times: list[int] = []
    for w, ms in zip(words, times_ms):
        if _normalize_caption_word(w):
            filtered_words.append(w)
            filtered_times.append(ms)

    return filtered_words, filtered_times


async def synthesize_all_slides(
    slides: List[SlideContent],
    audio_dir: str,
    language: str,
    voice_override: Optional[str] = None,
) -> List[str]:
    os.makedirs(audio_dir, exist_ok=True)
    voice = resolve_voice(language, voice_override)
    # #region agent log
    _agent_debug(
        "media.py:synthesize_all_slides",
        "tts batch start",
        "H1",
        {
            "language": language,
            "voice_override": voice_override,
            "resolved_voice": voice,
            "slide_count": len(slides),
            "max_concurrent": _TTS_MAX_CONCURRENT,
        },
    )
    # #endregion
    sem = asyncio.Semaphore(_TTS_MAX_CONCURRENT)
    paths: List[str] = []
    tasks = []

    async def _one(slide: SlideContent, out_path: str) -> None:
        async with sem:
            # Try to capture word timings for subtitle alignment; if this fails,
            # fall back to standard synthesis (still produces audio).
            try:
                w, ms = await _synthesize_slide_with_word_times(slide.narration or slide.title, out_path, voice)
                if w and ms and len(w) == len(ms):
                    slide.caption_words = w
                    slide.caption_times_ms = ms
            except Exception:
                await _synthesize_slide(slide.narration or slide.title, out_path, voice)

    for slide in slides:
        p = os.path.join(audio_dir, f"slide_{slide.index:02d}_tts.mp3")
        paths.append(p)
        tasks.append(asyncio.create_task(_one(slide, p)))
    await asyncio.gather(*tasks)
    # #region agent log
    _agent_debug(
        "media.py:synthesize_all_slides",
        "tts batch complete",
        "H-verify",
        {"slide_count": len(slides), "resolved_voice": voice},
        run_id="post-fix",
    )
    # #endregion
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

    await _synthesize_slide(text, output_path, voice)


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


def concatenate_audio(
    per_slide_paths: List[str],
    output_path: str,
    silence_between_ms: int = TTS_SILENCE_BETWEEN_MS,
) -> str:
    if not per_slide_paths:
        raise ValueError("No per-slide audio paths provided.")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    silence_path = os.path.join(os.path.dirname(output_path), "_silence.mp3")
    _create_silence(silence_path, duration_ms=silence_between_ms)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_file = f.name
        for i, p in enumerate(per_slide_paths):
            f.write(f"file '{os.path.abspath(p)}'\n")
            if i < len(per_slide_paths) - 1:
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
    silence_between_ms: int = TTS_SILENCE_BETWEEN_MS,
    last_slide_tail_seconds: float = 0.0,
) -> List[SlideContent]:
    """
    Match each slide's on-screen duration to the concatenated voiceover timeline:
    audio(segment_i) + silence between segments (except after the last).
    """
    def estimate_duration_seconds(text: str) -> float:
        words = re.findall(r"[A-Za-z0-9']+", text or "")
        word_count = max(1, len(words))
        wpm = 170.0
        seconds = word_count * (60.0 / wpm)
        seconds += 0.5
        return max(3.0, min(seconds, 30.0))

    n = len(slides)
    gap_sec = silence_between_ms / 1000.0

    for i, slide in enumerate(slides):
        if per_slide_tts_paths and i < len(per_slide_tts_paths):
            p = per_slide_tts_paths[i]
            if os.path.exists(p):
                try:
                    audio_sec = get_audio_duration(p)
                except Exception:
                    source_text = slide.narration or slide.title
                    audio_sec = estimate_duration_seconds(source_text)
                suffix = gap_sec if i < n - 1 else last_slide_tail_seconds
                slide.duration_seconds = max(0.5, audio_sec + suffix)
                continue
        slide.duration_seconds = 6.0
    return slides


def capture_slide_frames(
    html_path: str,
    slides: List[SlideContent],
    frames_dir: str,
    width: int,
    height: int,
    animation_settle_ms: int = 1200,
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
        exe = p.chromium.executable_path
        if not exe or not os.path.exists(exe):
            raise RuntimeError("Playwright Chromium is missing. Run: playwright install")
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            raise RuntimeError("Playwright Chromium launch failed. Run: playwright install") from e
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

    slides = compute_slide_durations(slides, per_slide_tts_paths=per_slide_tts)
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

