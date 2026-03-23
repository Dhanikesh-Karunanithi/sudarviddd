# SudarVid (HTML deck + optional MP4)

This project generates a themed interactive slide deck as `slides.html`, and can optionally export a rendered MP4 video.

## Start the backend

```powershell
python -m uvicorn sudarvid.server:app --reload --port 8000
```

Health check:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/health"
```

## Layout previews & learning-focused slides

- Open **`http://localhost:8000/design-previews`** for static thumbnails of each layout (hero, split learn, steps, contrast, stat focus, standard). These mirror the structures the HTML template renders; creative direction is aligned with ideas from [awesome-notebookLM-prompts](https://github.com/serenakeyitan/awesome-notebookLM-prompts).
- The content planner asks the LLM for **teaching-oriented** copy and a **`layout_kind`** per slide so decks are not only “image + title + bullets.”

### Text model (Together)

- **Default** slide planner model is **`openai/gpt-oss-20b`** — it follows the required JSON much more reliably than small “Thinker” models.
- For cheaper experiments you can set **`TOGETHER_TEXT_MODEL=ServiceNow-AI/Apriel-1.6-15b-Thinker`** in `.env`, but you may often get empty `slides` and see the **fallback** deck until you switch back.
- **JSON mode is on by default** (`response_format: json_object`). Set **`TOGETHER_JSON_RESPONSE=0`** (or `false` / `no` / `off`) only if your model rejects JSON mode on Together.

If jobs fail with **`Expecting value: line 1 column 1`** or **“Could not parse slide plan as JSON”**, try **`openai/gpt-oss-20b`** and/or ensure JSON mode is enabled. The planner also merges `content` + reasoning fields and extracts the first `{...}` object when the model adds extra prose.

### Pedagogy fields (API / YAML)

Optional fields help the planner align with a real curriculum (e.g. from **ByteOS**):

| Field | Role |
| --- | --- |
| `learning_objectives` | What learners should gain; steers slide outcomes |
| `difficulty` | e.g. `beginner`, `intermediate`, `advanced` |
| `source_notes` | Curriculum excerpt or facts the deck must respect |
| `constraints` | Include/avoid topics, jargon limits, exam board, etc. |

YAML configs ([`core.load_config`](sudarvid/core.py)) accept the same keys under the top-level object. The HTTP **`POST /generate`** body includes these fields as optional JSON properties.

### On-slide text length (optional tuning)

After the model returns slides, copy is compacted for layout. Defaults are slightly looser than before; override with env vars if needed:

- `SUDARVID_TITLE_MAX_WORDS`, `SUDARVID_TITLE_MAX_CHARS`
- `SUDARVID_SUBTITLE_MAX_WORDS`, `SUDARVID_SUBTITLE_MAX_CHARS`
- `SUDARVID_LEARNING_POINT_MAX_WORDS`, `SUDARVID_LEARNING_POINT_MAX_CHARS`
- `SUDARVID_STAT_CAPTION_MAX_WORDS`, `SUDARVID_STAT_CAPTION_MAX_CHARS`
- `SUDARVID_BULLET_MAX_WORDS`, `SUDARVID_BULLET_MAX_CHARS`

### Image model (Together)

- **Default** image model: **`black-forest-labs/FLUX.1-schnell`** (fast; good for iteration).
- For **sharper composition** at higher latency/cost, set **`TOGETHER_IMAGE_MODEL`** to a stronger image model available on your Together account (check their model list).
- **`TOGETHER_IMAGE_STEPS`**: diffusion steps for models that accept `steps` (default `6`). Omitted automatically for **`FLUX.2`** models that reject the parameter.
- Slide prompts stay **text-free** (words belong on the slide HTML, not in the bitmap). Each UI theme maps to a **style snippet** so backgrounds match the chosen theme.

### ByteOS integration

Use SudarVid as a **library** (`sudarvid.core.generate_video` with a `GenerationConfig`) or as an **HTTP service** (`POST /generate` then poll `GET /status/{job_id}`).

**Environment**

- **`TOGETHER_API_KEY`**: required for slide planning and image generation.

**Suggested mapping from ByteOS curriculum → SudarVid**

| ByteOS concept | SudarVid field |
| --- | --- |
| Module / lesson title | `topic` |
| Learner persona | `audience` |
| Locale | `language` |
| Module outcomes | `learning_objectives` |
| Level / track | `difficulty` |
| Syllabus bullets, textbook excerpt | `source_notes` |
| Brand or policy (“no medical claims”) | `constraints` |
| Free-form notes | `custom_content` |

Pin a **git tag or commit** of this repo in ByteOS so prompt and schema changes stay reproducible.

Example **`POST /generate`** body with curriculum context:

```json
{
  "topic": "Introduction to osmosis",
  "audience": "High school biology, ages 15–16",
  "language": "en",
  "theme": "seminar_minimal",
  "slide_count": 6,
  "learning_objectives": "Define osmosis; predict water flow direction; relate to equilibrium.",
  "difficulty": "beginner",
  "source_notes": "Cell membrane; semi-permeable; water potential (informal).",
  "constraints": "No clinical claims; keep to single-cell examples.",
  "include_tts": true,
  "output_html": true,
  "output_mp4": false
}
```

If **`slides.html` is empty** (no slides, no audio): the model often returned `"slides": []`, **`slides": null`**, or used a wrong key. The planner now reads several keys (`slides`, `slide`, `deck`, …), coerces a single object into a one-item list, and **falls back to a topic-based placeholder deck** so the job still produces playable HTML. Check the server stderr for **`[SudarVid] WARNING: Slide plan JSON contained no usable slides`**. Image API errors no longer cancel the whole job; failed slides simply have no background image.

## Generate an HTML preview with synced voiceover (no ffmpeg required)

This path generates:
- `output/<job_id>/slides.html`
- `output/<job_id>/audio/voiceover.mp3`

```powershell
$body = @{
  topic = "AI turns messy ideas into polished slides"
  audience = "general audience"
  language = "en"
  theme = "neo_retro_dev"
  slide_count = 3
  animation_level = "medium"
  include_tts = $true
  include_music = $false
  output_html = $true
  output_mp4 = $false
} | ConvertTo-Json -Depth 10

$r = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/generate" -ContentType "application/json" -Body $body
$r.job_id
```

Poll until done:

```powershell
$jobId = "<paste_job_id>"

do {
  $s = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/status/$jobId"
  Write-Host "status: $($s.status)"
  Start-Sleep -Seconds 5
} while ($s.status -ne "done" -and $s.status -ne "error")
```

Open:

- `output/<job_id>/slides.html`

The HTML uses the generated audio and the slide timing data to play like a video.

## Export MP4 video (requires ffmpeg + ffprobe)

MP4 export depends on `ffmpeg` and `ffprobe` being available on your `PATH`.

If `/health` reports `ffmpeg: false` or `ffprobe: false`, the MP4 job will fail.

When you want MP4, set:

- `output_mp4 = $true`
- `output_html = $true` (recommended)

