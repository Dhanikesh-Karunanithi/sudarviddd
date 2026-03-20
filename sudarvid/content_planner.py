from __future__ import annotations

import json
import os
import sys
from typing import Any, List, Optional

from together import Together

from .types import GenerationConfig, SlideContent


def _coerce_slides_array(value: Any) -> List[Any]:
    """JSON often has slides: null or a single object instead of an array."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _extract_slides_payload(data: dict) -> List[Any]:
    """Read slide objects from keys models commonly use."""
    for key in ("slides", "slide", "deck", "items", "pages"):
        raw = data.get(key)
        arr = _coerce_slides_array(raw)
        if arr:
            return arr
    return []


def _fallback_slides(config: GenerationConfig) -> List[SlideContent]:
    """
    If the LLM returns {} / [] / null slides, still emit a usable deck so jobs
    don't finish with an empty HTML file.
    """
    n = max(1, min(int(config.slide_count), 20))
    topic = (config.topic or "Presentation").strip() or "Presentation"
    out: List[SlideContent] = []
    for i in range(n):
        title = topic[:120] if i == 0 else f"{topic[:70]} — part {i + 1}"
        out.append(
            SlideContent(
                index=i,
                title=title,
                bullets=(
                    [
                        "The planner returned no slides in JSON (empty array, null, or wrong key).",
                        "Try TOGETHER_TEXT_MODEL=openai/gpt-oss-20b or set TOGETHER_JSON_RESPONSE=1.",
                        "Regenerate this job after fixing the model or prompt.",
                    ]
                    if i == 0
                    else [
                        "Replace this text by regenerating with a model that follows the JSON schema.",
                    ]
                ),
                narration=(
                    f"This is slide {i + 1} of {n} about {topic[:100]}. "
                    "The automatic slide planner did not return structured content."
                ),
                image_prompt=(
                    f"Vibrant abstract illustration suggesting: {topic[:180]}. "
                    "Editorial style, no text or typography in the image."
                ),
                layout_kind="hero" if i == 0 else "standard",
                subtitle="Fallback deck — AI returned no slide list" if i == 0 else None,
            )
        )
    return out


def _normalize_message_content(content: Any) -> str:
    """Together / OpenAI-style messages: str or list of {type, text} parts."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
                elif block.get("type") == "text" and isinstance(block.get("content"), str):
                    parts.append(block["content"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content)


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _first_balanced_json_object(text: str) -> Optional[str]:
    """Find first top-level {...} slice, respecting strings (handles nested braces)."""
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


def _parse_slide_plan_json(raw: str) -> dict:
    """
    Parse model output into a dict. Handles markdown fences, leading/trailing prose,
    and empty/garbled responses with a clear error.
    """
    raw = raw.strip()
    if not raw:
        raise RuntimeError(
            "Together returned an empty message for the slide plan. "
            "Try another TOGETHER_TEXT_MODEL or check API key / model access."
        )

    cleaned = _strip_markdown_fences(raw)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    blob = _first_balanced_json_object(cleaned) or _first_balanced_json_object(raw)
    if blob:
        try:
            return json.loads(blob)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                "Model returned text that looks like JSON but it failed to parse. "
                f"Parse error: {e}. First 400 chars: {blob[:400]!r}"
            ) from e

    # Last resort: array-only wrapper some models emit
    arr_start = cleaned.find("[")
    if arr_start >= 0:
        snippet = cleaned[arr_start:]
        depth = 0
        in_string = False
        escape = False
        for i, c in enumerate(snippet):
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
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    try:
                        slides = json.loads(snippet[: i + 1])
                        return {"slides": slides}
                    except json.JSONDecodeError:
                        break

    preview = raw[:500].replace("\n", "\\n")
    raise RuntimeError(
        "Could not parse slide plan as JSON (Expecting value often means the model "
        f"returned no JSON object). First 500 chars of response: {preview!r}"
    )


CONTENT_PLANNER_SYSTEM_PROMPT = """
You are the slide planning engine for an app called SudarVid.

Goal:
- Produce TEACHING / LEARNING content: each slide should help the viewer understand something new
  (definitions, cause-effect, steps, contrast, or a memorable stat), not generic marketing copy.
- Vary slide layouts so the video feels dynamic (inspired by editorial / NotebookLM-style decks:
  strong hierarchy, asymmetry, clear sections — see creative prompt collections for tone).

Constraints:
- Output strictly valid JSON matching this schema:
  {
    "slides": [
      {
        "title": "string",
        "bullets": ["string", ...],
        "narration": "string (~2-4 sentences, spoken, teaching tone)",
        "image_prompt": "string (for image generator, no line breaks, no text in image)",
        "layout_kind": "standard | hero | split_learn | steps | contrast | stat_focus",
        "subtitle": "string or empty — short hook under title (hero / split_learn)",
        "learning_point": "string or empty — one sentence: what the viewer should understand after this slide",
        "big_stat": "string or empty — e.g. 80%, 3x, Step 2 (for stat_focus / emphasis)",
        "stat_caption": "string or empty — label for big_stat"
      }
    ]
  }

layout_kind rules (use variety across the deck):
- hero: opening or chapter break; big idea + subtitle; 0-2 bullets max.
- split_learn: learning_point required; bullets are supporting facts (2-4).
- steps: bullets are ordered steps (use action verbs); learning_point can be empty.
- contrast: exactly 4 bullets: [concept A, detail A, concept B, detail B] for two-column compare.
- stat_focus: big_stat + stat_caption required; 1-3 short bullets for context.
- standard: classic title + bullets when nothing else fits.

Rules:
- 1 slide = 1 clear learning outcome.
- No markdown in any string. Plain text only for on-slide fields.
- All visible text and narration must be in the requested language.
- Tailor depth to the audience (explain terms for beginners; be denser for experts).
- image_prompt should match theme_id mood but never ask for readable text in the image.

Formatting:
- Return JSON only. No markdown.
""".strip()


def build_content_planner_user_prompt(config: GenerationConfig) -> str:
    return f"""
topic: {config.topic}
audience: {config.audience}
language: {config.language}
theme_id: {config.theme.value}
slide_count: {config.slide_count}

custom_content (may be empty):
{config.custom_content or ""}

Instructions:
- Vary layout_kind across slides (do not use only "standard").
- If slide_count >= 5, include at least one split_learn and at least one of steps or contrast.
- First slide should usually be hero.

Return JSON only, no markdown, no explanation.
""".strip()


class ContentPlanner:
    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
    ):
        if model is None:
            # gpt-oss-20b follows JSON slide schema reliably. "Thinker" / small models
            # often return empty slides or prose — use TOGETHER_TEXT_MODEL to experiment.
            model = os.environ.get(
                "TOGETHER_TEXT_MODEL",
                "openai/gpt-oss-20b",
            )
        self.client = Together(api_key=api_key)
        self.model = model

    def plan_slides(self, config: GenerationConfig) -> List[SlideContent]:
        user_prompt = build_content_planner_user_prompt(config)

        create_kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": CONTENT_PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.35,
            "max_tokens": 4096,
        }
        if os.environ.get("TOGETHER_JSON_RESPONSE", "").lower() in ("1", "true", "yes"):
            create_kwargs["response_format"] = {"type": "json_object"}

        resp = self.client.chat.completions.create(**create_kwargs)

        choice = resp.choices[0]
        msg = choice.message
        parts: List[str] = []
        main = _normalize_message_content(getattr(msg, "content", None))
        if main.strip():
            parts.append(main.strip())
        for attr in ("reasoning", "reasoning_content", "thinking"):
            extra = getattr(msg, attr, None)
            if isinstance(extra, str) and extra.strip():
                parts.append(extra.strip())

        raw = "\n\n".join(parts)

        if not raw.strip():
            finish = getattr(choice, "finish_reason", None)
            raise RuntimeError(
                "Together returned no usable text for the slide plan "
                f"(finish_reason={finish!r}). Try TOGETHER_TEXT_MODEL=openai/gpt-oss-20b "
                "or another JSON-friendly chat model."
            )

        data = _parse_slide_plan_json(raw)
        slides_data = _extract_slides_payload(data)

        allowed_layouts = frozenset(
            {"standard", "hero", "split_learn", "steps", "contrast", "stat_focus"}
        )

        slides: List[SlideContent] = []
        for idx, s in enumerate(slides_data):
            if not isinstance(s, dict):
                raise RuntimeError(
                    f"slides[{idx}] must be a JSON object, got {type(s).__name__!r}."
                )
            raw_layout = str(s.get("layout_kind", "standard") or "standard").strip().lower()
            layout = raw_layout if raw_layout in allowed_layouts else "standard"
            raw_bullets = s.get("bullets") or []
            if not isinstance(raw_bullets, list):
                raw_bullets = []
            bullets = [
                str(b).strip()
                for b in raw_bullets
                if b is not None and str(b).strip()
            ]
            slides.append(
                SlideContent(
                    index=idx,
                    title=str(s.get("title", "")).strip(),
                    bullets=bullets,
                    narration=str(s.get("narration", "")).strip(),
                    image_prompt=str(s.get("image_prompt", "")).strip(),
                    layout_kind=layout,
                    subtitle=(str(s.get("subtitle", "")).strip() or None),
                    learning_point=(str(s.get("learning_point", "")).strip() or None),
                    big_stat=(str(s.get("big_stat", "")).strip() or None),
                    stat_caption=(str(s.get("stat_caption", "")).strip() or None),
                )
            )

        if not slides:
            print(
                "[SudarVid] WARNING: Slide plan JSON contained no usable slides "
                f"(keys seen: {list(data.keys())!r}). Using topic-based fallback deck.",
                file=sys.stderr,
            )
            slides = _fallback_slides(config)
        else:
            target = max(1, int(config.slide_count))
            if len(slides) > target:
                slides = slides[:target]
            elif len(slides) < target:
                last = slides[-1]
                while len(slides) < target:
                    slides.append(
                        SlideContent(
                            index=len(slides),
                            title=last.title,
                            bullets=list(last.bullets),
                            narration=last.narration,
                            image_prompt=last.image_prompt,
                            layout_kind=last.layout_kind,
                            subtitle=last.subtitle,
                            learning_point=last.learning_point,
                            big_stat=last.big_stat,
                            stat_caption=last.stat_caption,
                        )
                    )

        for i, s in enumerate(slides):
            s.index = i
        return slides

