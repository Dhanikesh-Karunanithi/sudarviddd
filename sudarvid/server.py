from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sse_starlette.sse import EventSourceResponse

from .core import generate_video
from .image_models import IMAGE_MODELS, allowed_image_model_ids, normalize_image_model
from .loader_copy import generate_loader_copy_pack
from .media import (
    CURATED_TTS_VOICES,
    is_allowed_tts_voice,
    language_presets,
    preview_audio_cache_path,
    synthesize_tts_preview_file,
)
from .naming import allocate_job_folder_name
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
DEBUG_LOG_PATH = Path(os.environ.get("SUDARVID_LOG_DIR", tempfile.gettempdir())).resolve() / f"debug-{DEBUG_SESSION_ID}.log"


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


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = REPO_ROOT / "frontend"
DB_PATH = REPO_ROOT / "sudarvid.db"


job_events: Dict[str, asyncio.Queue] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS output_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
            """
        )
        conn.commit()


@app.on_event("startup")
async def startup_event() -> None:
    os.makedirs("output", exist_ok=True)
    _init_db()
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


def _create_job(job_id: str, output_dir: str) -> None:
    now = _utc_now_iso()
    with _db_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (id, status, output_dir, error, created_at, updated_at) VALUES (?, ?, ?, NULL, ?, ?)",
            (job_id, "queued", output_dir, now, now),
        )
        conn.commit()


def _set_job_status(job_id: str, status: str, error: Optional[str] = None) -> None:
    with _db_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
            (status, error, _utc_now_iso(), job_id),
        )
        conn.commit()


def _set_output_files(job_id: str, files: List[str]) -> None:
    with _db_conn() as conn:
        conn.execute("DELETE FROM output_files WHERE job_id = ?", (job_id,))
        for fp in files:
            conn.execute(
                "INSERT INTO output_files (job_id, file_path) VALUES (?, ?)",
                (job_id, fp),
            )
        conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (_utc_now_iso(), job_id))
        conn.commit()


def _get_job(job_id: str) -> Optional[dict]:
    with _db_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        files_rows = conn.execute(
            "SELECT file_path FROM output_files WHERE job_id = ? ORDER BY id ASC",
            (job_id,),
        ).fetchall()
    return {
        "job_id": row["id"],
        "status": row["status"],
        "output_dir": row["output_dir"],
        "output_files": [r["file_path"] for r in files_rows],
        "error": row["error"],
    }


async def _emit_progress(job_id: str, event: str, data: dict) -> None:
    queue = job_events.setdefault(job_id, asyncio.Queue())
    await queue.put({"event": event, "data": data})


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
        if rel_posix == "slides_manifest.json":
            found.append(rel_posix)
            continue
        if rel_posix in ("video/output.mp4", "audio/voiceover.mp3", "audio/music.mp3"):
            found.append(rel_posix)
            continue
        if "assets" in p.parts and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            found.append(rel_posix)
            continue

    return sorted(set(found))


def _try_open_slides_html(output_dir: str) -> None:
    # Set SUDARVID_OPEN_SLIDES=1 to open slides.html in the default app after a successful job.
    flag = os.environ.get("SUDARVID_OPEN_SLIDES", "").strip().lower()
    if flag not in ("1", "true", "yes"):
        return
    path = Path(output_dir).resolve() / "slides.html"
    if not path.is_file():
        return
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False, capture_output=True)
        else:
            opener = shutil.which("xdg-open")
            if opener:
                subprocess.run([opener, str(path)], check=False, capture_output=True)
    except Exception as e:
        print(f"[SudarVid] Could not open slides.html: {e}")


async def _run_job(job_id: str, config: GenerationConfig) -> None:
    loop = asyncio.get_running_loop()
    queue = job_events.setdefault(job_id, asyncio.Queue())

    def _progress_from_thread(event: str, payload: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, {"event": event, "data": payload})

    _set_job_status(job_id, "running")
    # Emit personalized loader copy ASAP (best-effort; always safe fallback).
    try:
        together_api_key = os.environ.get("TOGETHER_API_KEY", "")
        if together_api_key.strip():
            pack = await asyncio.to_thread(
                generate_loader_copy_pack,
                api_key=together_api_key,
                topic=config.topic,
                audience=config.audience,
                language=config.language,
                theme_id=config.theme.value,
            )
            await _emit_progress(job_id, "loader_copy", pack.to_dict())
    except Exception:
        # Never block job execution on loader copy.
        pass
    await _emit_progress(job_id, "status", {"status": "running", "step": "planning"})
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
            output_dir=os.path.join("output", job_id),
            config_obj=config,
            progress_callback=_progress_from_thread,
        )
        output_files = _collect_output_files(os.path.join("output", job_id))
        _set_output_files(job_id, output_files)
        _set_job_status(job_id, "done")
        await _emit_progress(job_id, "status", {"status": "done", "step": "done"})
        await asyncio.to_thread(_try_open_slides_html, os.path.join("output", job_id))
    except Exception as e:
        output_dir = Path("output").resolve() / job_id
        slides_path = output_dir / "slides.html"
        if slides_path.is_file():
            warning = f"MP4 generation issue: {e}"
            output_files = _collect_output_files(str(output_dir))
            _set_output_files(job_id, output_files)
            _set_job_status(job_id, "done", warning)
            await _emit_progress(
                job_id,
                "status",
                {"status": "done", "step": "done", "warning": warning, "error": warning},
            )
            print(f"[SudarVid] Job {job_id} completed with warning: {e}")
        else:
            _set_job_status(job_id, "error", str(e))
            await _emit_progress(job_id, "status", {"status": "error", "error": str(e)})
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
    learning_objectives: Optional[str] = Field(
        None,
        description="What learners should gain (bullets or short paragraph).",
        max_length=8000,
    )
    difficulty: Optional[str] = Field(
        None,
        description="e.g. beginner, intermediate, advanced.",
        max_length=120,
    )
    source_notes: Optional[str] = Field(
        None,
        description="Curriculum excerpt, outline, or facts the deck must align with.",
        max_length=16000,
    )
    constraints: Optional[str] = Field(
        None,
        description="What to include, avoid, or terminology limits.",
        max_length=8000,
    )
    persona: Optional[str] = Field(
        None,
        max_length=500,
        description="Named character or voice style for all narration and slide copy (the teacher/narrator, not the topic).",
    )
    voice_override: Optional[str] = Field(
        None,
        max_length=80,
        description="edge-tts voice name, e.g. en-US-GuyNeural (overrides language default).",
    )
    target_duration_seconds: Optional[float] = Field(
        None,
        ge=10.0,
        le=7200.0,
        description="Optional target total deck duration; slide timings scale toward this after audio is measured.",
    )
    image_model: Optional[str] = Field(
        None,
        max_length=120,
        description="Optional Together image model override. Empty/omitted means server auto/default.",
    )

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

    @field_validator("image_model")
    @classmethod
    def validate_image_model(cls, v: Optional[str]) -> Optional[str]:
        normalized = normalize_image_model(v)
        if normalized is None:
            return None
        if normalized not in allowed_image_model_ids():
            raise ValueError("Invalid image_model. Use GET /image-models for supported ids.")
        return normalized

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
            learning_objectives=self.learning_objectives,
            difficulty=self.difficulty,
            source_notes=self.source_notes,
            constraints=self.constraints,
            persona=self.persona,
            voice_override=self.voice_override,
            target_duration_seconds=self.target_duration_seconds,
            image_model=self.image_model,
        )


@app.get("/voices", summary="Languages and curated TTS voices for the creator UI")
async def get_voices() -> dict:
    return {"languages": language_presets(), "voices": CURATED_TTS_VOICES}


@app.get("/tts/preview", summary="Short MP3 sample for a voice (cached on disk)")
async def tts_preview(voice: str) -> FileResponse:
    v = (voice or "").strip()
    if not is_allowed_tts_voice(v):
        raise HTTPException(status_code=400, detail="Unknown or invalid voice id.")
    path = preview_audio_cache_path(v)
    if not path.is_file():
        try:
            await synthesize_tts_preview_file(v, path)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"TTS preview failed: {e}") from e
    return FileResponse(str(path), media_type="audio/mpeg", filename="preview.mp3")


@app.get("/export/{job_id}/bundle.zip", summary="Download job outputs as a zip (excludes frame captures)")
async def export_job_bundle(job_id: str) -> StreamingResponse:
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    base = Path(job["output_dir"]).resolve()
    if not base.is_dir():
        raise HTTPException(status_code=404, detail="Output folder not found.")

    buf = BytesIO()
    safe_name = f"{job_id}.zip"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if "frames" in p.parts:
                continue
            rel = p.relative_to(base)
            zf.write(p, rel.as_posix())
    data = buf.getvalue()

    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.get("/themes", summary="List all available themes")
async def get_themes() -> list:
    return list_themes()


@app.get("/image-models", summary="List curated Together image models for generation")
async def get_image_models() -> list:
    return IMAGE_MODELS


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
    job_id = allocate_job_folder_name(request.topic, "output")
    output_dir = os.path.join("output", job_id)
    os.makedirs(output_dir, exist_ok=True)

    config = request.to_generation_config()
    _create_job(job_id, output_dir)
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


@app.get("/jobs", summary="List recent jobs")
async def list_jobs(limit: int = 20, offset: int = 0) -> list:
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT id, status, created_at, updated_at, error FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


@app.get("/preview/{job_id}", summary="Open the generated slide deck (redirect to rendered HTML)")
async def preview_job_deck(job_id: str) -> RedirectResponse:
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return RedirectResponse(url=f"/render/{job_id}/slides.html")


@app.get("/v/{job_id}", summary="Legacy preview redirect (backward compatibility)")
async def legacy_v_preview_redirect(job_id: str) -> RedirectResponse:
    # Older frontend versions redirected to `/v/<job_id>`; keep this working.
    return RedirectResponse(url=f"/preview/{job_id}")


@app.get("/status/{job_id}", summary="Check job status")
async def get_status(job_id: str) -> dict:
    job = _get_job(job_id)
    if not job:
        _debug_log(
            hypothesis_id="H1_jobid_polling_format",
            location="server.py:get_status:not_found",
            message="job not found for requested job_id",
            data={"job_id": job_id},
        )
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "output_files": job["output_files"],
        "error": job["error"],
    }


@app.get("/api/jobs/{job_id}/slides", summary="Slide manifest (layout + visual_template per slide)")
async def get_job_slides_manifest(job_id: str) -> List[dict]:
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    path = Path(job["output_dir"]).resolve() / "slides_manifest.json"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="slides_manifest.json not found (job may still be running or was created before this feature).",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/stream/{job_id}", summary="Stream job progress updates")
async def stream_status(job_id: str) -> EventSourceResponse:
    if not _get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    queue = job_events.setdefault(job_id, asyncio.Queue())

    async def event_generator():
        last_status = None
        while True:
            job = _get_job(job_id)
            if not job:
                yield {"event": "status", "data": json.dumps({"status": "missing"})}
                break

            if job["status"] != last_status:
                last_status = job["status"]
                yield {
                    "event": "status",
                    "data": json.dumps(
                        {
                            "job_id": job_id,
                            "status": job["status"],
                            "error": job["error"],
                            "output_files": job["output_files"],
                        }
                    ),
                }

            try:
                queued = await asyncio.wait_for(queue.get(), timeout=1.5)
                yield {"event": queued["event"], "data": json.dumps(queued["data"])}
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": json.dumps({"ts": time.time()})}

            if job["status"] in ("done", "error"):
                break

    return EventSourceResponse(event_generator())


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
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    base = Path(job["output_dir"]).resolve()
    file_path = (Path(job["output_dir"]) / filename).resolve()
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
        content_disposition_type="inline",
    )


@app.get("/health")
async def health() -> dict:
    playwright_chromium_ok = False
    playwright_note = ""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            exe = p.chromium.executable_path
            playwright_chromium_ok = bool(exe and os.path.exists(exe))
            if not playwright_chromium_ok:
                playwright_note = "Run: playwright install"
    except Exception:
        playwright_note = "Run: playwright install"
    return {
        "status": "ok",
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "playwright_chromium_ok": playwright_chromium_ok,
        "playwright_note": playwright_note,
    }


# SPA: register API routes above, then serve `frontend/` (index.html + assets).
# html=True returns index.html for missing paths so `/v/<job_id>` (SPA preview) works client-side.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
