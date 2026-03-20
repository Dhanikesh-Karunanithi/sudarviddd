from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, field_validator

from .core import generate_video
from .themes import list_themes
from .types import AnimationLevel, GenerationConfig, ThemeId, VideoSize


app = FastAPI(
    title="SudarVid API",
    description="AI-powered animated slide video generator",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEBUG_SESSION_ID = "5d97eb"
DEBUG_LOG_PATH = Path(__file__).resolve().parents[1] / "debug-5d97eb.log"


def _debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: Optional[dict] = None,
    run_id: str = "pre-fix",
) -> None:
    """
    Minimal NDJSON instrumentation for debugging. Never include secrets/tokens.
    """
    try:
        payload = {
            "sessionId": DEBUG_SESSION_ID,
            "id": f"log_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
            "timestamp": int(time.time() * 1000),
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
        }
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Never fail the server because debug logging failed.
        pass


@app.on_event("startup")
async def startup_event() -> None:
    os.makedirs("output", exist_ok=True)
    ffmpeg_exists = bool(shutil.which("ffmpeg"))
    ffprobe_exists = bool(shutil.which("ffprobe"))
    _debug_log(
        hypothesis_id="H3_ffmpeg_missing",
        location="server.py:startup_event",
        message="ffmpeg/ffprobe availability",
        data={"ffmpeg": ffmpeg_exists, "ffprobe": ffprobe_exists},
    )
    if not ffmpeg_exists:
        print("[SudarVid] WARNING: ffmpeg not found in PATH. MP4 output will fail.")
    if not ffprobe_exists:
        print("[SudarVid] WARNING: ffprobe not found in PATH. Audio duration detection may fail.")


@dataclass
class JobState:
    id: str
    status: str  # queued | running | done | error
    output_dir: str
    output_files: List[str] = field(default_factory=list)
    error: Optional[str] = None


jobs: Dict[str, JobState] = {}


def _collect_output_files(output_dir: str) -> List[str]:
    base = Path(output_dir).resolve()
    found: List[str] = []
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if "frames" in p.parts:
            continue

        rel = p.relative_to(base)
        rel_posix = rel.as_posix()

        if rel_posix == "slides.html":
            found.append(rel_posix)
            continue
        if rel_posix in ("video/output.mp4", "audio/voiceover.mp3", "audio/music.mp3"):
            found.append(rel_posix)
            continue

    return sorted(set(found))


async def _run_job(job_id: str, config: GenerationConfig) -> None:
    job = jobs[job_id]
    job.status = "running"
    try:
        _debug_log(
            hypothesis_id="H2_model_not_available",
            location="server.py:_run_job:start",
            message="job started",
            data={"job_id": job_id, "theme": config.theme.value, "output_mp4": config.output_mp4, "include_tts": config.include_tts},
        )
        await asyncio.to_thread(
            generate_video,
            config_path=None,
            output_dir=job.output_dir,
            config_obj=config,
        )
        job.output_files = _collect_output_files(job.output_dir)
        job.status = "done"
    except Exception as e:
        job.error = str(e)
        job.status = "error"
        print(f"[SudarVid] Job {job_id} failed: {e}")
        _debug_log(
            hypothesis_id="H2_model_not_available",
            location="server.py:_run_job:error",
            message="job failed",
            data={"job_id": job_id, "error": str(e)[:500]},
        )


class VideoSizeRequest(BaseModel):
    width: int = Field(1920, ge=320, le=7680)
    height: int = Field(1080, ge=180, le=7680)


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    audience: str = Field("general audience", max_length=200)
    language: str = Field("en", max_length=10)
    theme: str = Field("neo_retro_dev")
    slide_count: int = Field(5, ge=3, le=20)
    video_size: VideoSizeRequest = Field(default_factory=VideoSizeRequest)
    animation_level: str = Field("medium")
    include_tts: bool = True
    include_music: bool = True
    output_html: bool = True
    output_mp4: bool = True
    custom_content: Optional[str] = None

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        valid = [t["id"] for t in list_themes()]
        if v not in valid:
            raise ValueError(f"Invalid theme '{v}'. Choose from: {valid}")
        return v

    @field_validator("animation_level")
    @classmethod
    def validate_animation_level(cls, v: str) -> str:
        valid = ["subtle", "medium", "dynamic"]
        if v not in valid:
            raise ValueError(f"Invalid animation_level '{v}'. Choose from: {valid}")
        return v

    def to_generation_config(self) -> GenerationConfig:
        return GenerationConfig(
            topic=self.topic,
            audience=self.audience,
            language=self.language,
            theme=ThemeId(self.theme),
            slide_count=self.slide_count,
            video_size=VideoSize(width=self.video_size.width, height=self.video_size.height),
            animation_level=AnimationLevel(self.animation_level),
            include_tts=self.include_tts,
            include_music=self.include_music,
            output_html=self.output_html,
            output_mp4=self.output_mp4,
            custom_content=self.custom_content,
        )


@app.get("/themes", summary="List all available themes")
async def get_themes() -> list:
    return list_themes()


@app.get("/sizes", summary="List preset video sizes")
async def get_sizes() -> list:
    return [
        {"label": "Landscape 16:9", "width": 1920, "height": 1080},
        {"label": "Portrait 9:16", "width": 1080, "height": 1920},
        {"label": "Square 1:1", "width": 1080, "height": 1080},
        {"label": "Widescreen 21:9", "width": 2560, "height": 1080},
        {"label": "Custom", "width": None, "height": None},
    ]


@app.post("/generate", summary="Start a video generation job")
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = str(uuid.uuid4())
    output_dir = os.path.join("output", job_id)
    os.makedirs(output_dir, exist_ok=True)

    config = request.to_generation_config()
    jobs[job_id] = JobState(id=job_id, status="queued", output_dir=output_dir)
    _debug_log(
        hypothesis_id="H1_jobid_polling_format",
        location="server.py:generate",
        message="job created",
        data={
            "job_id": job_id,
            "output_dir": output_dir,
            "theme": config.theme.value,
            "include_tts": config.include_tts,
            "include_music": config.include_music,
            "output_html": config.output_html,
            "output_mp4": config.output_mp4,
        },
    )
    background_tasks.add_task(_run_job, job_id, config)

    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}", summary="Check job status")
async def get_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        _debug_log(
            hypothesis_id="H1_jobid_polling_format",
            location="server.py:get_status:not_found",
            message="job not found for requested job_id",
            data={"job_id": job_id},
        )
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {
        "job_id": job.id,
        "status": job.status,
        "output_files": job.output_files,
        "error": job.error,
    }


MIME_MAP = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


@app.get("/download/{job_id}/{filename:path}", summary="Download an output file")
async def download_file(job_id: str, filename: str) -> FileResponse:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    base = Path(job.output_dir).resolve()
    file_path = (Path(job.output_dir) / filename).resolve()
    if base not in file_path.parents and file_path != base:
        raise HTTPException(status_code=404, detail="File not found.")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")

    media_type = MIME_MAP.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )


@app.get("/render/{job_id}/{filename:path}", summary="Serve a generated output file (for preview)")
async def render_job_file(job_id: str, filename: str) -> FileResponse:
    """
    Serve files from output/<job_id>/... so that slides.html can load:
    - audio/voiceover.mp3 (relative URL)
    - static/js/sudarvid.js (relative URL)
    - assets/... images (relative URL)

    This enables reliable iframe previewing.
    """
    output_root = Path("output").resolve() / job_id
    base = output_root.resolve()
    file_path = (output_root / filename).resolve()

    # Basic traversal prevention.
    if base not in file_path.parents and file_path != base:
        raise HTTPException(status_code=404, detail="File not found.")

    # Avoid serving large intermediate frame captures.
    if "frames" in file_path.parts:
        raise HTTPException(status_code=404, detail="File not found.")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")

    media_type = MIME_MAP.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )


@app.get("/design-previews", summary="Static previews of slide layouts (no generation)")
async def design_previews() -> HTMLResponse:
    return HTMLResponse(
        """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SudarVid — layout previews</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; padding: 24px;
      background: #0f1115; color: #eaeef5; }
    h1 { margin: 0 0 8px; font-size: 1.35rem; }
    p.lead { opacity: 0.85; font-size: 14px; max-width: 52rem; margin-bottom: 20px; }
    a { color: #93c5fd; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
    .card { background: #161a22; border: 1px solid #2a3140; border-radius: 12px; padding: 14px; }
    .card h2 { margin: 0 0 10px; font-size: 13px; letter-spacing: 0.06em; text-transform: uppercase; color: #93c5fd; }
    .stage { width: 100%; aspect-ratio: 16 / 9; background: #0b0d12; border-radius: 8px; overflow: hidden;
      position: relative; font-size: 7px; }
    .mini { position: absolute; inset: 0; padding: 14px 16px; color: #f1f5f9; font-family: Georgia, serif; }
    .accent { color: #38bdf8; }
    .bar { height: 3px; width: 36px; background: #38bdf8; margin: 4px 0 8px; border-radius: 1px; }
    .t { font-weight: 800; font-size: 11px; line-height: 1.1; margin-bottom: 4px; }
    .st { font-size: 6px; opacity: 0.85; margin-bottom: 6px; font-family: system-ui, sans-serif; }
    .bul { margin: 0; padding-left: 1em; font-family: system-ui, sans-serif; font-size: 6px; line-height: 1.4; }
    .learn { border-left: 3px solid #38bdf8; padding: 6px 8px; background: rgba(255,255,255,.06); border-radius: 0 6px 6px 0;
      font-family: system-ui, sans-serif; font-size: 6px; margin-bottom: 4px; }
    .bc { display: flex; flex-direction: column; gap: 3px; }
    .pill { padding: 4px 6px 4px 18px; background: rgba(255,255,255,.07); border-radius: 5px;
      font-family: system-ui, sans-serif; font-size: 6px; position: relative; }
    .pill::before { content: "01"; position: absolute; left: 4px; font-weight: 800; color: #38bdf8; font-size: 7px; }
    .cg { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 4px; }
    .cc { padding: 5px 6px; background: rgba(255,255,255,.06); border-top: 2px solid #38bdf8; border-radius: 0 0 5px 5px; }
    .cc h3 { margin: 0 0 2px; font-size: 7px; }
    .cc p { margin: 0; font-size: 6px; opacity: 0.9; font-family: system-ui, sans-serif; }
    .big { font-size: 22px; font-weight: 800; color: #38bdf8; line-height: 1; }
    .split { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; align-items: start; }
  </style>
</head>
<body>
  <h1>Slide layout previews</h1>
  <p class="lead">These mock the <strong>learning layouts</strong> SudarVid can render (hero, split learn, steps, contrast, stat focus, standard).
    Real decks add theme fonts, generated images, and timed voiceover. Inspired by editorial / NotebookLM-style prompt ideas such as
    <a href="https://github.com/serenakeyitan/awesome-notebookLM-prompts" target="_blank" rel="noreferrer">awesome-notebookLM-prompts</a>.
    <a href="/">← Back to tester</a></p>
  <div class="grid">
    <div class="card"><h2>hero</h2><div class="stage"><div class="mini">
      <div class="accent" style="font-size:5px;letter-spacing:.15em;">01 / 05</div>
      <div class="bar"></div>
      <div class="t">Big idea</div>
      <div class="st">Short hook that frames why this matters.</div>
    </div></div></div>
    <div class="card"><h2>split_learn</h2><div class="stage"><div class="mini split">
      <div>
        <div class="learn"><strong style="color:#38bdf8;">Learning focus</strong><br/>One sentence outcome for the viewer.</div>
      </div>
      <div class="bc">
        <div class="pill">Supporting fact one</div>
        <div class="pill" style="padding-left:18px;">Fact two</div>
      </div>
      <div style="grid-column:1/-1;"><div class="t" style="font-size:9px;">Slide title</div></div>
    </div></div></div>
    <div class="card"><h2>steps</h2><div class="stage"><div class="mini">
      <div class="bar"></div>
      <div class="t" style="font-size:9px;">How it works</div>
      <div class="pill">Do this first</div>
      <div class="pill" style="padding-left:18px;"><span style="position:absolute;left:4px;color:#38bdf8;font-weight:800;">02</span>Then this</div>
    </div></div></div>
    <div class="card"><h2>contrast</h2><div class="stage"><div class="mini">
      <div class="t" style="font-size:8px;">Compare</div>
      <div class="cg">
        <div class="cc"><h3>Concept A</h3><p>Detail for side A.</p></div>
        <div class="cc"><h3>Concept B</h3><p>Detail for side B.</p></div>
      </div>
    </div></div></div>
    <div class="card"><h2>stat_focus</h2><div class="stage"><div class="mini">
      <div class="t" style="font-size:8px;">Proof point</div>
      <div class="big">3×</div>
      <div class="st" style="max-width:12em;">Caption explaining the number.</div>
      <ul class="bul"><li>Context bullet</li></ul>
    </div></div></div>
    <div class="card"><h2>standard</h2><div class="stage"><div class="mini">
      <div class="bar"></div>
      <div class="t" style="font-size:9px;">Title</div>
      <ul class="bul"><li>Classic bullet list</li><li>Second point</li></ul>
    </div></div></div>
  </div>
</body>
</html>
""",
        status_code=200,
    )


@app.get("/", summary="SudarVid test UI")
async def ui_root() -> HTMLResponse:
    return HTMLResponse(
        """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SudarVid Tester</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 20px; background: #0f1115; color: #eaeef5; }
    .row { display: flex; gap: 16px; flex-wrap: wrap; }
    .card { background: #161a22; border: 1px solid #2a3140; border-radius: 12px; padding: 16px; flex: 1 1 340px; }
    label { display: block; font-size: 12px; opacity: 0.9; margin-bottom: 6px; }
    input, select, textarea { width: 100%; background: #0b0d12; color: #eaeef5; border: 1px solid #2a3140; border-radius: 10px; padding: 10px; margin-bottom: 12px; }
    textarea { min-height: 84px; resize: vertical; }
    button { background: #3b82f6; border: 0; color: white; padding: 10px 14px; border-radius: 10px; cursor: pointer; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    a { color: #93c5fd; }
    .muted { opacity: 0.8; font-size: 12px; }
    #previewFrame { width: 100%; height: 540px; border: 1px solid #2a3140; border-radius: 12px; background: #000; }
    .status { white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  </style>
</head>
<body>
  <h1 style="margin: 0 0 14px 0;">SudarVid Tester</h1>
  <p class="muted" style="margin:0 0 16px 0;">
    <a href="/design-previews">Layout &amp; component previews</a> (static demos, no API) ·
    Slide structures borrow ideas from <a href="https://github.com/serenakeyitan/awesome-notebookLM-prompts" target="_blank" rel="noreferrer">awesome-notebookLM-prompts</a>.
  </p>

  <div class="row">
    <div class="card">
      <h3 style="margin-top:0;">1) Generate</h3>
      <label>Topic</label>
      <textarea id="topic">AI turns messy ideas into polished slide decks</textarea>

      <label>Audience</label>
      <input id="audience" value="general audience" />

      <label>Language</label>
      <input id="language" value="en" />

      <label>Theme</label>
      <select id="theme"></select>

      <label>Slide count</label>
      <input id="slideCount" value="5" />

      <label>Animation level</label>
      <select id="animationLevel">
        <option value="subtle">subtle</option>
        <option value="medium" selected>medium</option>
        <option value="dynamic">dynamic</option>
      </select>

      <div class="muted">For now: MP4 export requires ffmpeg/ffprobe.</div>
      <button id="btnGenerate">Generate (HTML+audio only)</button>
      <div style="margin-top:10px;" class="status" id="status"></div>
    </div>

    <div class="card">
      <h3 style="margin-top:0;">2) Preview existing job</h3>
      <label>Job ID</label>
      <input id="jobId" placeholder="e.g. 019d01e3-711f-47ef-b361-995776b788bc" />

      <button id="btnLoadExisting" style="background:#22c55e;">Load preview</button>

      <div style="margin-top:12px;">
        <div class="muted">Preview uses relative URLs, served from <code>/render/&lt;job_id&gt;/...</code>.</div>
        <iframe id="previewFrame" src="about:blank"></iframe>
      </div>
      <div style="margin-top:10px;" class="muted">
        MP4 link (if generated): <a id="mp4Link" href="#" target="_blank" rel="noreferrer">output.mp4</a>
      </div>
    </div>
  </div>

  <script>
    const $ = (id) => document.getElementById(id);

    function setStatus(s) { $("status").textContent = s; }

    function getQueryJobId() {
      try {
        const u = new URL(window.location.href);
        return u.searchParams.get("job_id") || "";
      } catch { return ""; }
    }

    async function loadThemes() {
      const res = await fetch("/themes");
      const themes = await res.json();
      const sel = $("theme");
      sel.innerHTML = "";
      for (const t of themes) {
        const opt = document.createElement("option");
        opt.value = t.id;
        opt.textContent = t.label + " (" + t.id + ")";
        sel.appendChild(opt);
      }
      // Prefer neo_retro_dev if present.
      sel.value = "neo_retro_dev";
    }

    function buildPreviewSrc(jobId) {
      // Serve slides.html and its relative assets via /render/<jobId>/...
      return "/render/" + encodeURIComponent(jobId) + "/slides.html";
    }

    async function loadExisting() {
      const jobId = $("jobId").value.trim();
      if (!jobId) { alert("Paste a job_id first."); return; }
      $("previewFrame").src = buildPreviewSrc(jobId);
      $("mp4Link").href = "/render/" + encodeURIComponent(jobId) + "/video/output.mp4";
    }

    async function generate() {
      setStatus("Starting job...");
      $("btnGenerate").disabled = true;
      $("btnGenerate").textContent = "Generating...";

      const body = {
        topic: $("topic").value,
        audience: $("audience").value,
        language: $("language").value,
        theme: $("theme").value,
        slide_count: parseInt($("slideCount").value, 10),
        animation_level: $("animationLevel").value,
        include_tts: true,
        include_music: false,
        output_html: true,
        output_mp4: false
      };

      const res = await fetch("/generate", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(body)
      });
      const data = await res.json();
      const jobId = data.job_id;
      setStatus("job_id: " + jobId + "\\nstatus: queued");

      // Poll status.
      while (true) {
        await new Promise(r => setTimeout(r, 2000));
        const sRes = await fetch("/status/" + encodeURIComponent(jobId));
        const s = await sRes.json();
        setStatus("job_id: " + s.job_id + "\\nstatus: " + s.status + (s.error ? "\\nerror: " + s.error : ""));
        if (s.status === "done") {
          $("jobId").value = jobId;
          $("previewFrame").src = buildPreviewSrc(jobId);
          $("mp4Link").href = "/render/" + encodeURIComponent(jobId) + "/video/output.mp4";
          break;
        }
        if (s.status === "error") break;
      }

      $("btnGenerate").disabled = false;
      $("btnGenerate").textContent = "Generate (HTML+audio only)";
    }

    $("btnLoadExisting").addEventListener("click", loadExisting);
    $("btnGenerate").addEventListener("click", generate);

    loadThemes().then(() => {
      const qJobId = getQueryJobId();
      if (qJobId) {
        $("jobId").value = qJobId;
        $("previewFrame").src = buildPreviewSrc(qJobId);
        $("mp4Link").href = "/render/" + encodeURIComponent(qJobId) + "/video/output.mp4";
      }
    });
  </script>
</body>
</html>
""",
        status_code=200,
    )


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
    }

