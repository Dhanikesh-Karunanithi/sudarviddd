Now I have the full picture of every file in the codebase. Let me compile the complete assessment.

***

# SudarVid — Full Codebase Improvement Plan for Cursor

This is a complete file-by-file assessment with actionable fixes across all 9 modules of the project.

***

## 🗂️ Architecture Overview (as-is)

The pipeline is: `POST /generate` → `content_planner.py` (LLM) → `image_gen.py` (Together FLUX) → `media.py` (edge-tts + ffmpeg) → `core.py` (Jinja2 HTML render) → `server.py` (FastAPI + SQLite). [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

***

## 🔴 CRITICAL BUGS

### Bug 1 — Persona/Style Is Silently Swallowed (`content_planner.py`)

**Root cause:** `CONTENT_PLANNER_SYSTEM_PROMPT` has no concept of persona or stylistic voice.  When you send `"topic": "Introduction to Management as taught by Michael Scott"`, the entire string lands in the `topic:` line of `build_content_planner_user_prompt()`, but the system prompt never instructs the LLM to extract and honor a persona qualifier. The model treats it as a topic title and strips the character entirely. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

**Fix — Add a `persona` field to `GenerationConfig` and `GenerateRequest`:**

In `types.py`, add to `GenerationConfig`:
```python
persona: Optional[str] = None  
# e.g. "Michael Scott from The Office — humorous, self-important, accidentally wise"
```

In `server.py` `GenerateRequest`, add:
```python
persona: Optional[str] = Field(None, max_length=500,
    description="A named character or voice style for all narration and slide copy.")
```

In `content_planner.py`, update `build_content_planner_user_prompt()`:
```python
# Add this block before the Instructions section:
if config.persona:
    prompt += f"\npersona / voice style: {config.persona}"
    prompt += "\nIMPORTANT: Write ALL narration, bullets, titles, and subtitles in this persona's voice."
    prompt += " The persona is not the subject — it is the TEACHER delivering the content."
```

Also update `CONTENT_PLANNER_SYSTEM_PROMPT` to add:
```
- If a persona is specified, ALL slide text and narration must be written in that character's voice and style.
  The persona is the NARRATOR and TEACHER, not the topic. Do not ignore it or reduce it to a subtitle.
```

***

### Bug 2 — Audio Doesn't Play in HTML Preview (`core.py` + `media.py`)

**Root cause 1 — Double TTS synthesis with no reuse:** When `output_mp4=True`, `generate_video()` in `core.py` synthesizes TTS once (lines ~60-70 in core.py) to get durations and build `voiceover.mp3` for the HTML deck. Then `build_full_video()` in `media.py` synthesizes TTS *again* from scratch. The second synthesis creates a new set of per-slide files in the same `audio/` folder, **overwriting the `voiceover.mp3`** that was just correctly linked in `slides.html`. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

**Fix — Pass the already-synthesized voiceover path to `build_full_video`:**

In `core.py`, change the MP4 section:
```python
# BEFORE (broken):
if config.output_mp4:
    mp4_path = build_full_video(config, slides, html_path=html_path, output_dir=output_dir)

# AFTER (fixed):
if config.output_mp4:
    # Reuse already-synthesized voiceover_path; don't re-synthesize
    mp4_path = build_full_video(
        config, slides, html_path=html_path, output_dir=output_dir,
        existing_voiceover_path=voiceover_path,        # pass it through
        existing_per_slide_tts=per_slide_tts,
    )
```

In `media.py`, update `build_full_video` signature:
```python
def build_full_video(
    config, slides, html_path, output_dir,
    custom_music_path=None,
    existing_voiceover_path=None,    # NEW
    existing_per_slide_tts=None,     # NEW
):
    ...
    if existing_voiceover_path and os.path.exists(existing_voiceover_path):
        voiceover_path = existing_voiceover_path
        per_slide_tts = existing_per_slide_tts
    elif config.include_tts:
        per_slide_tts = asyncio.run(synthesize_all_slides(...))
        ...
```

**Root cause 2 — `include_tts=False` but audio element still present:** When `include_tts=False`, the Jinja2 template in `base.html.j2` should not emit the `<audio id="SudarVidVoiceover">` element at all. If it does, the JS player will log `"Audio failed to load"` and block user interaction. Check `base.html.j2` for:
```jinja
{% if include_tts %}
<audio id="SudarVidVoiceover" src="audio/voiceover.mp3" preload="auto"></audio>
{% endif %}
```
Make sure this conditional exists and is correct.

**Root cause 3 — Browser autoplay blocking:** `sudarvid-3.js` tries `audio.play()` on page load. Browsers require a user gesture first. The current fallback (`hint.textContent = "Audio blocked..."`) is easy to miss.  Add a prominent click-to-play overlay: [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/dffc7a22-66fa-459d-8c59-7b0f0d0ad4ec/sudarvid-3.js)

In `sudarvid-3.js`, replace the `audioBlocked` hint update with:
```javascript
if (audioBlocked) {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;cursor:pointer';
    overlay.innerHTML = '<div style="background:#fff;padding:2rem 3rem;border-radius:12px;font-size:1.4rem;font-weight:bold;">▶ Click anywhere to play with audio</div>';
    overlay.addEventListener('click', () => { overlay.remove(); play(); });
    document.body.appendChild(overlay);
}
```

***

### Bug 3 — `include_music` Flag Is Completely Non-Functional (`core.py` + `media.py`)

`include_music: bool` exists in `GenerationConfig` and `GenerateRequest`, but `build_full_video` only uses music when `custom_music_path` is externally provided.  There is zero code that auto-sources or generates background music. The frontend likely shows a "Include Music" checkbox that does nothing. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

**Fix — Either remove the flag from the UI or wire it up:**

Option A (quick fix): In `server.py`, add to the `/generate` endpoint docs:
```python
include_music: bool = Field(False, description="Reserved for future use. No music source is wired yet.")
```
And in `base.html.j2`, if the music element is rendered, wrap it in a condition checking if `music.mp3` exists.

Option B (proper fix): Integrate a royalty-free music API (e.g., Pixabay API, or locally-bundled ambient loops). Store a few royalty-free ambient MP3s in `static/music/` and select one based on theme:
```python
THEME_MUSIC_MAP = {
    "sports": "static/music/energetic.mp3",
    "seminar_minimal": "static/music/ambient_soft.mp3",
    "neo_retro_dev": "static/music/retro_synth.mp3",
    # ...
}
```

***

## 🟡 SIGNIFICANT ISSUES

### Issue 4 — Image Generation Has No Retry or Seed Consistency (`image_gen.py`)

Currently, a single exception on any slide simply sets `slide.image_path = None` with no retry.  There is also no shared seed across slides, so the same theme can yield wildly different art styles per run. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

**Fix — Add retry + per-job seed:**

```python
import random

class ImageGenerator:
    def generate_for_slides(self, config, slides, progress_callback=None):
        job_seed = random.randint(1, 2**31)  # consistent across this run
        
        for idx, slide in enumerate(slides, start=1):
            ...
            for attempt in range(3):  # retry up to 3 times
                try:
                    payload = {
                        ...
                        "seed": job_seed + slide.index,  # deterministic per-slide
                    }
                    # existing API call
                    break  # success, exit retry loop
                except Exception as e:
                    if attempt == 2:
                        print(f"[SudarVid] WARNING: Image gen failed for slide {slide.index} after 3 attempts: {e}")
                    else:
                        time.sleep(2 ** attempt)  # exponential back-off
```

Also add a placeholder image generator as a last resort:
```python
def _generate_placeholder_image(output_path: str, slide_title: str, theme: ThemeSpec) -> None:
    """Creates a minimal colored PNG placeholder when API fails."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1920, 1080), color=theme.bg_color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 1880, 1040], outline=theme.accent_color, width=8)
    img.save(output_path)
```

***

### Issue 5 — Slide Duration Cap Is Too Restrictive (`media.py`)

`compute_slide_durations` caps duration at `max(2.0, min(seconds, 12.0))`.  If TTS generates 18 seconds of audio for a dense slide (ffprobe path), the cap is bypassed because ffprobe returns the real duration. But the **heuristic fallback** caps at 12 seconds, which is too short for educational content. Also, the 150 WPM reading rate is too slow — TTS voices typically speak at 160–180 WPM. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

**Fix in `media.py`:**
```python
def estimate_duration_seconds(text: str) -> float:
    words = re.findall(r"[A-Za-z0-9']+", text or "")
    word_count = max(1, len(words))
    wpm = 170.0  # closer to real edge-tts rate
    seconds = word_count * (60.0 / wpm)
    seconds += 0.5  # natural pause
    return max(3.0, min(seconds, 30.0))  # raise ceiling to 30s
```

***

### Issue 6 — Temperature Is Too Low for Creative Content (`content_planner.py`)

The `_chat_json` method uses `temperature=0.35` for all content generation.  This makes sense for structured JSON output but produces generic, dry copy. For persona-driven or creative content, a two-pass approach is better: [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

```python
# In _chat_json, accept a temperature param:
def _chat_json(self, system: str, user: str, temperature: float = 0.35) -> dict:
    ...

# In plan_slides, use higher temperature for persona content:
def plan_slides(self, config: GenerationConfig) -> List[SlideContent]:
    temp = 0.7 if config.persona else 0.4
    data = self._chat_json(CONTENT_PLANNER_SYSTEM_PROMPT, user_prompt, temperature=temp)
```

***

### Issue 7 — `target_duration_seconds` Is Declared But Never Used (`core.py` + `types.py`)

`GenerationConfig` has a `target_duration_seconds` field that's loaded from YAML and the API, but nowhere in `generate_video()` or downstream is it referenced.  This means users who set `target_duration_seconds: 90` get a deck that ignores their request. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

**Fix:** After TTS synthesis and `compute_slide_durations`, add proportional rescaling:
```python
if config.target_duration_seconds:
    actual_total = sum(s.duration_seconds for s in slides)
    scale = config.target_duration_seconds / max(actual_total, 1.0)
    if 0.5 < scale < 2.0:  # only rescale within sane bounds
        for s in slides:
            s.duration_seconds = max(3.0, s.duration_seconds * scale)
```

***

### Issue 8 — Security: Secrets and Debug Data Committed to Repo (`server.py` + repo root)

`debug-5d97eb.log` and `sudarvid.db` (SQLite with job history) are committed to the repository.  These should be in `.gitignore`. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

**Fix — Update `.gitignore`:**
```
*.log
*.db
output/
.env
__pycache__/
*.pyc
```

Also, `DEBUG_LOG_PATH` writes to the **repository root**, not a temp/log directory. This means every server run appends to a committed file:
```python
# Change in server.py:
DEBUG_LOG_PATH = Path(os.environ.get("SUDARVID_LOG_DIR", "/tmp")) / f"debug-{DEBUG_SESSION_ID}.log"
```

***

## 🟢 IMPROVEMENTS & ENHANCEMENTS

### Enhancement 1 — Add `voice` Field to Override TTS Voice (`types.py` + `media.py`)

Currently, voice is determined solely by language with no user override.  Some users may want a male voice, different accent, or a specific edge-tts voice. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

```python
# In types.py GenerationConfig:
voice_override: Optional[str] = None  # e.g. "en-US-GuyNeural"

# In media.py resolve_voice():
def resolve_voice(language: str, voice_override: Optional[str] = None) -> str:
    if voice_override:
        return voice_override
    return VOICE_MAP.get(language.lower(), "en-US-AriaNeural")
```

***

### Enhancement 2 — Add More TTS Voices to `VOICE_MAP` (`media.py`)

The current map has 11 languages but only one voice per language.  Edge-TTS supports dozens. Add gendered alternatives and expand coverage: [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

```python
VOICE_MAP = {
    "en": "en-US-AriaNeural",
    "en-male": "en-US-GuyNeural",
    "en-uk": "en-GB-SoniaNeural",
    "en-uk-male": "en-GB-RyanNeural",
    "en-au": "en-AU-NatashaNeural",
    "ta": "ta-IN-PallaviNeural",   # Tamil
    "te": "te-IN-ShrutiNeural",    # Telugu  
    "ml": "ml-IN-SobhanaNeural",   # Malayalam
    "bn": "bn-IN-TanishaaNeural",  # Bengali
    # ... existing entries ...
}
```

***

### Enhancement 3 — `_collect_output_files` Misses Generated Images (`server.py`)

The function that populates `output_files` in the job record only captures `slides.html`, `slides_manifest.json`, and audio/video.  Generated images in `assets/images/` are completely excluded. This means the `/download/{job_id}/` endpoint can't serve slide images directly. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

```python
def _collect_output_files(output_dir: str) -> List[str]:
    ...
    # ADD this block:
    if "assets" in p.parts and p.suffix.lower() in (".png", ".jpg", ".webp"):
        found.append(rel_posix)
        continue
```

***

### Enhancement 4 — Add a `GET /jobs` Endpoint for Job History (`server.py`)

There is no endpoint to list past jobs. The SQLite `jobs` table exists but is only queryable by `job_id`.  Add: [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

```python
@app.get("/jobs", summary="List recent jobs")
async def list_jobs(limit: int = 20, offset: int = 0) -> list:
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT id, status, created_at, updated_at, error FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    return [dict(r) for r in rows]
```

***

### Enhancement 5 — Add `GET /preview/{job_id}` Redirect (`server.py`)

Currently, to view the generated HTML deck, users must manually open the file or construct a `/render/` URL. Add a convenience redirect:

```python
@app.get("/preview/{job_id}", summary="Open the generated slide deck in browser")
async def preview_job(job_id: str):
    from fastapi.responses import RedirectResponse
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return RedirectResponse(url=f"/render/{job_id}/slides.html")
```

***

### Enhancement 6 — Web Fonts Are Not Loaded (`themes.py` + `base.html.j2`)

All 18 themes use system font stacks (`'Impact'`, `'Arial Black'`, `'Courier New'`).  On macOS and Linux, `Impact` is not available, causing all bold headings to fall back to a generic sans-serif that looks nothing like the intended design. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/82229814/13927f78-716a-4812-9b4b-1a4610f0d5a5/slides_manifest-2.json)

**Fix:** For each theme, add a `google_fonts_url` field to `ThemeSpec`:
```python
@dataclass(frozen=True)
class ThemeSpec:
    ...
    google_fonts_url: str = ""  # e.g. "https://fonts.googleapis.com/css2?family=Oswald:wght@700&display=swap"
```

Then in `base.html.j2`:
```jinja
{% if theme.google_fonts_url %}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="{{ theme.google_fonts_url }}" rel="stylesheet">
{% endif %}
```

Example mappings:
| Theme | Suggested Google Font |
|---|---|
| `neo_retro_dev` | Space Grotesk + Space Mono |
| `seminar_minimal` | Inter |
| `manga` | Bangers |
| `sports` | Oswald 700 |
| `magazine` | Playfair Display |
| `modern_newspaper` | DM Sans |

***

## 📋 Priority Order for Cursor

| Priority | File(s) | Issue | Impact |
|---|---|---|---|
| 🔴 P0 | `content_planner.py`, `types.py`, `server.py` | Add `persona` field + inject into system prompt | Fixes ALL persona/style content failures |
| 🔴 P0 | `core.py`, `media.py` | Stop double-synthesizing TTS; pass voiceover path to `build_full_video` | Fixes overwritten audio |
| 🔴 P0 | `base.html.j2`, `sudarvid-3.js` | Add click-to-play overlay for blocked audio | Fixes silent video on first load |
| 🟡 P1 | `content_planner.py` | Raise temperature to 0.7 for persona content | Better creative copy |
| 🟡 P1 | `image_gen.py` | Add 3-attempt retry with exponential backoff + per-job seed | Stops broken/inconsistent images |
| 🟡 P1 | `media.py` | Fix duration heuristic WPM + raise 12s ceiling to 30s | Fixes slide timing drift |
| 🟡 P1 | `core.py` | Wire `target_duration_seconds` to proportional rescaling | Honors user-set duration |
| 🟡 P1 | `server.py` | Fix `_collect_output_files` to include `assets/images/` | Images downloadable via API |
| 🟢 P2 | `server.py` | Add `GET /jobs` list endpoint + `GET /preview/{job_id}` redirect | Better usability |
| 🟢 P2 | `media.py`, `types.py` | Add `voice_override` field + expand `VOICE_MAP` with Indian languages | Broader audience support |
| 🟢 P2 | `server.py` | Move `DEBUG_LOG_PATH` out of repo root; update `.gitignore` | Security hygiene |
| 🟢 P2 | `themes.py`, `base.html.j2` | Add `google_fonts_url` per theme + load in template | Visual quality on all OS |
| 🟢 P3 | `server.py` | Wire `include_music` to bundled royalty-free music or remove from UI | No more no-op checkbox |