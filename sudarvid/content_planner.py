from __future__ import annotations

import json
import os
import sys
from typing import Any, List, Optional

from together import Together

from .types import GenerationConfig, SlideContent

VISUAL_TEMPLATES = frozenset(
    {
        "full_bleed_bg",
        "split_right",
        "split_left",
        "top_band",
        "inset_card",
        "none",
    }
)


def _default_visual_template(layout_kind: str) -> str:
    """When the planner omits visual_template, use a sensible default per pedagogy layout."""
    return {
        "hero": "top_band",
        "split_learn": "split_right",
        "steps": "split_left",
        "contrast": "inset_card",
        "stat_focus": "top_band",
        "standard": "full_bleed_bg",
    }.get(layout_kind, "full_bleed_bg")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _json_response_enabled() -> bool:
    """Default on; set TOGETHER_JSON_RESPONSE=0|false|no|off to disable."""
    v = os.environ.get("TOGETHER_JSON_RESPONSE", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _truncate_text(value: Optional[str], max_words: int, max_chars: int) -> Optional[str]:
    if not value:
        return None
    words = [w for w in str(value).strip().split() if w]
    if max_words > 0 and len(words) > max_words:
        words = words[:max_words]
    text = " ".join(words).strip()
    if max_chars > 0 and len(text) > max_chars:
        text = text[: max_chars - 1].rstrip(" ,;:-") + "…"
    return text or None


def _compact_slide_text(slide: SlideContent) -> SlideContent:
    """Tighten on-slide copy; limits overridable via SUDARVID_* env vars."""
    bullet_limits = {
        "hero": 2,
        "split_learn": 3,
        "steps": 4,
        "contrast": 4,
        "stat_focus": 3,
        "standard": 4,
    }
    max_bullets = bullet_limits.get(slide.layout_kind, 4)
    bw = _env_int("SUDARVID_BULLET_MAX_WORDS", 18)
    bc = _env_int("SUDARVID_BULLET_MAX_CHARS", 100)
    compact_bullets: List[str] = []
    for b in slide.bullets[:max_bullets]:
        t = _truncate_text(b, max_words=bw, max_chars=bc)
        if t:
            compact_bullets.append(t)

    slide.title = (
        _truncate_text(
            slide.title,
            max_words=_env_int("SUDARVID_TITLE_MAX_WORDS", 12),
            max_chars=_env_int("SUDARVID_TITLE_MAX_CHARS", 88),
        )
        or "Untitled slide"
    )
    slide.subtitle = _truncate_text(
        slide.subtitle,
        max_words=_env_int("SUDARVID_SUBTITLE_MAX_WORDS", 18),
        max_chars=_env_int("SUDARVID_SUBTITLE_MAX_CHARS", 108),
    )
    slide.learning_point = _truncate_text(
        slide.learning_point,
        max_words=_env_int("SUDARVID_LEARNING_POINT_MAX_WORDS", 20),
        max_chars=_env_int("SUDARVID_LEARNING_POINT_MAX_CHARS", 128),
    )
    slide.stat_caption = _truncate_text(
        slide.stat_caption,
        max_words=_env_int("SUDARVID_STAT_CAPTION_MAX_WORDS", 12),
        max_chars=_env_int("SUDARVID_STAT_CAPTION_MAX_CHARS", 72),
    )
    slide.bullets = compact_bullets
    return slide


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
                visual_template="top_band" if i == 0 else "full_bleed_bg",
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
- Produce TEACHING / LEARNING content: each slide must help the viewer understand something concrete
  (definition, cause-effect, ordered steps, contrast, worked implication, or a memorable stat with context).
- Avoid filler: no vague bullets like "important concept", "key takeaway", "things to know" without naming
  what specifically (use nouns, numbers, named relationships, or short examples).
- Vary slide layouts so the video feels dynamic (editorial / NotebookLM-style: hierarchy, asymmetry, sections).

Quality rubric (every slide must pass):
- Title states the micro-topic in plain language (not clickbait).
- At least one bullet or the narration names a specific idea, example, or distinction (not only adjectives).
- learning_point (when used) states what the learner can DO or EXPLAIN after the slide.
- Narration: 2–4 spoken sentences; teach in order (define → explain → example or implication); do not read bullets verbatim.

image_prompt rubric (for a text-free diffusion image):
- Describe ONE clear scene or metaphor: subject + setting + mood + composition (e.g. wide shot, single focal object).
  Match theme_id mood.
- Do NOT ask for charts, maps, books, signage, UI, HUD, screenshots, labeled diagrams, scientific figures with labels,
  posters with writing, or any readable text in the image.

visual_template (where the image appears in the slide frame — choose per slide for variety):
- full_bleed_bg: soft full-screen background behind text (decorative; image is low prominence).
- split_right: text column left, image in a framed card on the right (best for metaphors and concepts).
- split_left: image card left, text right.
- top_band: wide image strip on top, content below (strong for hero and chapter breaks).
- inset_card: smaller framed image (e.g. corner or side) so text stays primary (dense slides).
- none: no image (text-only slide; omit image-heavy prompts).

Constraints:
- Output strictly valid JSON matching this schema:
  {
    "slides": [
      {
        "title": "string",
        "bullets": ["string", ...],
        "narration": "string (~2-4 sentences, spoken, teaching tone)",
        "image_prompt": "string (single line; subject + setting + mood + composition; no text in image)",
        "layout_kind": "standard | hero | split_learn | steps | contrast | stat_focus",
        "visual_template": "full_bleed_bg | split_right | split_left | top_band | inset_card | none",
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
- Tailor depth using difficulty and audience (define jargon for beginners; use denser links for advanced).

Compact example (tone only; do not copy topics):
{"slides":[{"title":"What is osmosis","bullets":["Water moves through a semi-permeable membrane toward higher solute concentration","Net flow stops at equilibrium"],"narration":"Osmosis is net movement of water across a membrane toward where solutes are more concentrated. At equilibrium, water movement balances and concentrations stabilize.","image_prompt":"Single glass beaker with water and a subtle membrane divider, soft lab lighting, centered subject","layout_kind":"split_learn","visual_template":"split_right","subtitle":"","learning_point":"Learners can explain direction of water flow across a membrane","big_stat":"","stat_caption":""}]}

Formatting:
- Return JSON only. No markdown.
""".strip()


CONTENT_EXTENDER_SYSTEM_PROMPT = """
You extend an existing SudarVid teaching deck. The learner already saw the slides listed in the user message.
Add NEW slides only — do not repeat titles or re-cover the same subtopics.

Same JSON schema as the main planner: {"slides":[...]} with the same fields per slide, including visual_template.
Quality: same rubric — concrete teaching, no vague bullets; image_prompt = one metaphor, no text in image;
vary visual_template across new slides.
Return JSON only. No markdown.
""".strip()


def _optional_block(label: str, value: Optional[str]) -> str:
    v = (value or "").strip()
    if not v:
        return f"{label}: (none)"
    return f"{label}:\n{v}"


def build_content_planner_user_prompt(config: GenerationConfig) -> str:
    return f"""
topic: {config.topic}
audience: {config.audience}
language: {config.language}
theme_id: {config.theme.value}
slide_count: {config.slide_count}
difficulty: {config.difficulty or "(not specified; infer from audience)"}

{_optional_block("learning_objectives", config.learning_objectives)}
{_optional_block("source_notes (curriculum alignment)", config.source_notes)}
{_optional_block("constraints (include/avoid)", config.constraints)}

custom_content (may be empty):
{config.custom_content or ""}

Instructions:
- If learning_objectives or source_notes are provided, align every slide to them; do not invent unrelated scope.
- If difficulty is set, match explanation depth to that level.
- Vary layout_kind across slides (do not use only "standard").
- Vary visual_template across slides (do not use only full_bleed_bg; use split_* and top_band for stronger visuals).
- If slide_count >= 5, include at least one split_learn and at least one of steps or contrast.
- First slide should usually be hero with visual_template top_band or full_bleed_bg.
- For split_learn and steps slides, set learning_point when it helps the learner verify understanding.

Return JSON only, no markdown, no explanation.
""".strip()


def _parse_slide_dict(idx: int, s: Any, allowed_layouts: frozenset) -> SlideContent:
    if not isinstance(s, dict):
        raise RuntimeError(f"slides[{idx}] must be a JSON object, got {type(s).__name__!r}.")
    raw_layout = str(s.get("layout_kind", "standard") or "standard").strip().lower()
    layout = raw_layout if raw_layout in allowed_layouts else "standard"
    raw_bullets = s.get("bullets") or []
    if not isinstance(raw_bullets, list):
        raw_bullets = []
    bullets = [str(b).strip() for b in raw_bullets if b is not None and str(b).strip()]
    raw_vt = str(s.get("visual_template", "") or "").strip().lower()
    visual_template = raw_vt if raw_vt in VISUAL_TEMPLATES else _default_visual_template(layout)
    return SlideContent(
        index=idx,
        title=str(s.get("title", "")).strip(),
        bullets=bullets,
        narration=str(s.get("narration", "")).strip(),
        image_prompt=str(s.get("image_prompt", "")).strip(),
        layout_kind=layout,
        visual_template=visual_template,
        subtitle=(str(s.get("subtitle", "")).strip() or None),
        learning_point=(str(s.get("learning_point", "")).strip() or None),
        big_stat=(str(s.get("big_stat", "")).strip() or None),
        stat_caption=(str(s.get("stat_caption", "")).strip() or None),
    )


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

    def _chat_json(self, system: str, user: str) -> dict:
        create_kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.35,
            "max_tokens": 4096,
        }
        if _json_response_enabled():
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
        return _parse_slide_plan_json(raw)

    def _extend_slides(
        self,
        existing: List[SlideContent],
        config: GenerationConfig,
        need_count: int,
        allowed_layouts: frozenset,
    ) -> List[SlideContent]:
        if need_count <= 0:
            return []
        lines: List[str] = []
        for i, sl in enumerate(existing, start=1):
            bpreview = ", ".join(sl.bullets[:4]) if sl.bullets else ""
            lp = sl.learning_point or ""
            lines.append(
                f"{i}. [{sl.layout_kind}] {sl.title}"
                + (f" | {lp}" if lp else "")
                + (f" | {bpreview}" if bpreview else "")
            )
        summary = "\n".join(lines)
        user = f"""
topic: {config.topic}
audience: {config.audience}
language: {config.language}
theme_id: {config.theme.value}
difficulty: {config.difficulty or "(infer)"}

{_optional_block("learning_objectives", config.learning_objectives)}
{_optional_block("source_notes", config.source_notes)}
{_optional_block("constraints", config.constraints)}

Existing slides (do not repeat or lightly rephrase these; add genuinely new teaching steps):
{summary}

Generate exactly {need_count} NEW slides continuing the teaching arc (deeper detail, application, common mistake,
summary, or next subtopic). Return JSON with a "slides" array.
""".strip()

        try:
            data = self._chat_json(CONTENT_EXTENDER_SYSTEM_PROMPT, user)
        except Exception as e:
            print(
                f"[SudarVid] WARNING: Could not extend deck via LLM ({e!s}). "
                f"Keeping {len(existing)} slides (short of requested {config.slide_count}).",
                file=sys.stderr,
            )
            return []

        slides_data = _extract_slides_payload(data)
        start = len(existing)
        out: List[SlideContent] = []
        for j, s in enumerate(slides_data):
            if len(out) >= need_count:
                break
            try:
                out.append(_parse_slide_dict(start + j, s, allowed_layouts))
            except RuntimeError:
                continue
        return out

    def plan_slides(self, config: GenerationConfig) -> List[SlideContent]:
        user_prompt = build_content_planner_user_prompt(config)

        data = self._chat_json(CONTENT_PLANNER_SYSTEM_PROMPT, user_prompt)
        slides_data = _extract_slides_payload(data)

        allowed_layouts = frozenset(
            {"standard", "hero", "split_learn", "steps", "contrast", "stat_focus"}
        )

        slides: List[SlideContent] = []
        for idx, s in enumerate(slides_data):
            slides.append(_parse_slide_dict(idx, s, allowed_layouts))

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
                need = target - len(slides)
                extra = self._extend_slides(slides, config, need, allowed_layouts)
                slides = slides + extra
                if len(slides) > target:
                    slides = slides[:target]
                if len(slides) < target:
                    print(
                        "[SudarVid] WARNING: Deck has fewer slides than requested "
                        f"({len(slides)} < {target}) after extension; not padding with duplicates.",
                        file=sys.stderr,
                    )

        for i, s in enumerate(slides):
            s.index = i
            _compact_slide_text(s)
        return slides

