from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, Optional

from together import Together


_DEFAULT_STEPS: Dict[str, str] = {
    "plan": "Plotting your scenes…",
    "images": "Generating images…",
    "audio": "Creating narration…",
    "render": "Building slide deck…",
    "rendering_video": "Encoding video file…",
}


@dataclass(frozen=True)
class LoaderCopyPack:
    metaphor: str
    subtitle: str
    steps: Dict[str, str]

    def to_dict(self) -> dict:
        return {
            "metaphor": self.metaphor,
            "subtitle": self.subtitle,
            "steps": self.steps,
        }


LOADER_COPY_SYSTEM_PROMPT = """
You write short loading/progress copy for an app called SudarVid.

Goal:
- Personalize the loader copy to the user's topic using a metaphor (e.g., "car_build", "space_mission", "kitchen", "studio", "lab").
- Keep each string short (<= 52 characters is ideal; never exceed 80).
- Use ellipses (…) not three dots. No emojis.
- Do NOT mention model names, providers, or "LLM".
- Keep it generic/safe (no sensitive claims, no personal data).

Output strictly valid JSON only, matching:
{
  "metaphor": "string",
  "subtitle": "string",
  "steps": {
    "plan": "string",
    "images": "string",
    "audio": "string",
    "render": "string",
    "rendering_video": "string"
  }
}
""".strip()


def _strip_markdown_fences(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _first_balanced_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_json_object(raw: str) -> Optional[dict]:
    cleaned = _strip_markdown_fences(raw or "")
    if not cleaned.strip():
        return None
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    blob = _first_balanced_json_object(cleaned) or _first_balanced_json_object(raw or "")
    if not blob:
        return None
    try:
        obj = json.loads(blob)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _one_line(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _normalize_ellipsis(s: str) -> str:
    s = _one_line(s)
    s = s.replace("...", "…")
    return s


def _safe_text(s: str, max_len: int) -> str:
    s = _normalize_ellipsis(s)
    s = s.replace("\u0000", "")
    s = re.sub(r"[`*_#>\[\]{}]", "", s).strip()
    s = re.sub(r"\s+…", "…", s)
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip(" ,;:-") + "…"
    return s


def _coerce_steps(steps: object) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if isinstance(steps, dict):
        for k in ("plan", "images", "audio", "render", "rendering_video"):
            v = steps.get(k)
            if isinstance(v, str) and v.strip():
                out[k] = v.strip()
    return out


def _fallback_pack(topic: str) -> LoaderCopyPack:
    t = (topic or "").strip().lower()

    # A tiny heuristic layer so it feels personalized even without LLM.
    if any(x in t for x in ("llm", "language model", "transformer", "gpt", "ai", "neural", "machine learning")):
        metaphor = "ai_lab"
        subtitle = "Assembling your lesson…"
        steps = {
            "plan": "Sketching the architecture…",
            "images": "Training the visuals…",
            "audio": "Synthesizing narration…",
            "render": "Packaging the deck…",
            "rendering_video": "Running the final eval…",
        }
    elif any(x in t for x in ("biology", "neuro", "brain", "cell", "medical", "health", "anatomy")):
        metaphor = "lab"
        subtitle = "Preparing your explainer…"
        steps = {
            "plan": "Setting up the experiment…",
            "images": "Preparing slide visuals…",
            "audio": "Recording narration…",
            "render": "Compiling the results…",
            "rendering_video": "Publishing the video…",
        }
    elif any(x in t for x in ("finance", "invest", "stock", "econom", "account", "tax")):
        metaphor = "workbench"
        subtitle = "Putting your lesson together…"
        steps = {
            "plan": "Outlining the strategy…",
            "images": "Drafting visuals…",
            "audio": "Adding narration…",
            "render": "Assembling the deck…",
            "rendering_video": "Finalizing the export…",
        }
    else:
        metaphor = "workshop"
        subtitle = "Building your lesson…"
        steps = {
            "plan": "Drafting the blueprint…",
            "images": "Crafting the visuals…",
            "audio": "Adding the voiceover…",
            "render": "Assembling the deck…",
            "rendering_video": "Final render pass…",
        }

    # Safety normalization and bounds.
    clean_steps = {k: _safe_text(steps.get(k, _DEFAULT_STEPS[k]), 80) for k in _DEFAULT_STEPS.keys()}
    return LoaderCopyPack(
        metaphor=_safe_text(metaphor, 24) or "workshop",
        subtitle=_safe_text(subtitle, 80) or "Building your lesson…",
        steps=clean_steps,
    )


def generate_loader_copy_pack(
    *,
    api_key: str,
    topic: str,
    audience: str,
    language: str,
    theme_id: str,
) -> LoaderCopyPack:
    """
    Best-effort, fast loader copy generation.
    Never raises; always returns a valid pack.
    """
    model = os.environ.get("TOGETHER_LOADER_MODEL", "").strip() or os.environ.get("TOGETHER_TEXT_MODEL", "").strip()
    if not model:
        return _fallback_pack(topic)

    user_prompt = f"""
topic: {topic}
audience: {audience}
language: {language}
theme_id: {theme_id}

Write a metaphor pack for the loader stages.
Return JSON only.
""".strip()

    try:
        client = Together(api_key=api_key)
        create_kwargs: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": LOADER_COPY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.6,
            "max_tokens": 512,
        }
        # Many Together chat models support JSON response_format; if they don't, parsing still falls back.
        create_kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**create_kwargs)

        choice = resp.choices[0]
        msg = choice.message
        raw = ""
        main = getattr(msg, "content", None)
        if isinstance(main, str):
            raw = main
        else:
            raw = str(main or "")

        data = _parse_json_object(raw)
        if not isinstance(data, dict):
            return _fallback_pack(topic)

        metaphor = _safe_text(str(data.get("metaphor", "") or ""), 24) or "workshop"
        subtitle = _safe_text(str(data.get("subtitle", "") or ""), 80) or "Building your lesson…"
        steps_in = _coerce_steps(data.get("steps"))
        steps = {k: _safe_text(steps_in.get(k, _DEFAULT_STEPS[k]), 80) for k in _DEFAULT_STEPS.keys()}
        return LoaderCopyPack(metaphor=metaphor, subtitle=subtitle, steps=steps)
    except Exception:
        return _fallback_pack(topic)

