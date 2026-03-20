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
- Add **`TOGETHER_JSON_RESPONSE=1`** if Together supports JSON mode for your chosen model (stricter `{...}` output).

If jobs fail with **`Expecting value: line 1 column 1`** or **“Could not parse slide plan as JSON”**, try **`openai/gpt-oss-20b`** and/or **`TOGETHER_JSON_RESPONSE=1`**. The planner also merges `content` + reasoning fields and extracts the first `{...}` object when the model adds extra prose.

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

