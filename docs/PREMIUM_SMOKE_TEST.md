# Premium Mode Smoke Test

Use this checklist after integration changes to ensure premium mode remains stable and classic mode is not regressed.

## 1) Start server

```powershell
python -m uvicorn sudarvid.server:app --reload --port 8000
```

## 2) Submit premium job

```powershell
$body = @{
  topic = "Behavioral economics for product teams"
  audience = "product managers and designers"
  language = "en"
  theme = "studio_premium"
  slide_count = 8
  animation_level = "medium"
  include_tts = $true
  include_music = $false
  output_html = $true
  output_mp4 = $false
  learning_objectives = "Explain anchoring, loss aversion, and social proof with product examples."
  difficulty = "intermediate"
  engine_mode = "premium"
} | ConvertTo-Json -Depth 10

$r = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/generate" -ContentType "application/json" -Body $body
$r
```

Expected:

- Response includes `job_id`, `status=queued`, and `meta.engine_mode=premium`.

## 3) Poll status

```powershell
$jobId = $r.job_id
do {
  $s = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/status/$jobId"
  $s
  Start-Sleep -Seconds 3
} while ($s.status -ne "done" -and $s.status -ne "error")
```

Expected on success:

- `status=done`
- `meta.engine_mode=premium`
- `output_files` contains `slides.html` and `slides_manifest.json`.

## 4) Visual/runtime checks (manual)

Open:

- `http://localhost:8000/render/$jobId/slides.html`

Verify:

- Scene-based premium layout renders.
- Timeline pill shows `current / total` time.
- Chapter chips navigate scenes.
- Keyboard controls work (`Space`, arrows).
- Quiz/interaction panels render without JS errors.

## 5) API contract checks

- `GET /status/{job_id}` includes `meta` object.
- `GET /stream/{job_id}` status events include `meta`.
- `slides_manifest.json` includes `interaction_type` where available.

## 6) Classic-mode regression check

Run same request with:

- `engine_mode = "classic"`

Confirm:

- Existing classic deck output remains unchanged.
- No premium-only markup/behavior leaks into classic render.

