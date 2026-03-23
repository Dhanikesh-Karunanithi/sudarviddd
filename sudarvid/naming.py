from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Windows-forbidden in file names; also avoid path separators.
_UNSAFE = re.compile(r'[\\/:*?"<>|]+')


def slugify_topic(topic: str, max_len: int = 50) -> str:
    s = topic.strip().lower()
    s = _UNSAFE.sub("", s)
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "project"
    return s[:max_len].rstrip("_") or "project"


def allocate_job_folder_name(topic: str, output_root: str) -> str:
    """
    Human-readable id: {slug}_{YYYYMMDD_HHMMSS_utc}_{shortuniq} with collision handling.
    Safe for use as a single path segment (no slashes).
    """
    slug = slugify_topic(topic)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    root = Path(output_root)
    for _ in range(256):
        candidate = f"{slug}_{ts}_{uuid.uuid4().hex[:8]}"
        if not (root / candidate).exists():
            return candidate
    return f"{slug}_{ts}_{uuid.uuid4().hex[:16]}"
