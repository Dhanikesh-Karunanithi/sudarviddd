from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, TypedDict


SpriteMode = Literal["auto", "library_only", "ai_preferred"]
MotionLevel = Literal["low", "medium", "high"]
TextDensity = Literal["compact", "balanced", "detailed"]
TopicFamily = Literal["programming", "science", "history", "finance", "general"]


class SpriteFact(TypedDict):
    year: str
    cat: str
    text: str


class RenderPayload(TypedDict):
    topic: str
    objective: str
    score_label: str
    facts: List[SpriteFact]
    theme_id: str
    template_id: str
    motion_level: MotionLevel
    text_density: TextDensity
    sprite_mode: SpriteMode
    topic_family: TopicFamily
    sprites: List[List[List[int]]]


@dataclass(frozen=True)
class TemplateMeta:
    id: str
    label: str
    motion_profile: str
    text_profile: str
    preferred_topics: List[str]
    asset_mode: str


DEFAULT_PYTHON_FACTS: List[SpriteFact] = [
    {"year": "START", "cat": "PYTHON BASICS", "text": "Python is a beginner-friendly language.\nThink of it as giving clear step-by-step instructions to your computer."},
    {"year": "IDEA", "cat": "PROGRAMS = RECIPES", "text": "A program is like a cooking recipe.\nYou write steps in order, and Python follows them exactly."},
    {"year": "STEP 1", "cat": "PRINT()", "text": "print() makes Python speak on screen.\nReal-world example: print('Hello') is like saying hello out loud."},
    {"year": "STEP 2", "cat": "VARIABLES", "text": "Variables are labeled boxes for information.\nname='Asha' means the box called name stores Asha."},
    {"year": "STEP 3", "cat": "DATA TYPES", "text": "Different data types are different kinds of things:\ntext ('hi'), numbers (42), and true/false values."},
    {"year": "STEP 4", "cat": "LISTS", "text": "A list is like a shopping list.\n['milk','bread','eggs'] stores many items in one place."},
    {"year": "STEP 5", "cat": "IF STATEMENTS", "text": "if helps Python choose.\nIf it rains, carry umbrella; else, carry sunglasses."},
    {"year": "STEP 6", "cat": "LOOPS", "text": "Loops repeat tasks automatically.\nLike watering 5 plants one-by-one without rewriting the same instruction."},
    {"year": "STEP 7", "cat": "FUNCTIONS", "text": "Functions are reusable mini-recipes.\nDefine once, call many times: useful for greetings, bills, or reports."},
    {"year": "PRACTICE", "cat": "LEARN BY DOING", "text": "Errors are clues, not failure.\nTry this tiny challenge: print your name, age, and favorite hobby."},
]

_LAST_TEMPLATE_ID = "player_lesson_modern"

TEMPLATES: Dict[str, TemplateMeta] = {
    "player_lesson_modern": TemplateMeta("player_lesson_modern", "Player Lesson Modern", "smooth", "guided", ["programming", "general"], "ui"),
    "ide_walkthrough": TemplateMeta("ide_walkthrough", "IDE Walkthrough", "steady", "technical", ["programming", "science"], "code"),
    "concept_cards_motion": TemplateMeta("concept_cards_motion", "Concept Cards Motion", "minimal", "concise", ["science", "finance", "general"], "card"),
    "quiz_showcase": TemplateMeta("quiz_showcase", "Quiz Showcase", "interactive", "guided", ["programming", "science", "general"], "quiz"),
    "cinematic_cards": TemplateMeta("cinematic_cards", "Cinematic Cards", "dramatic", "story", ["history", "general"], "card"),
    "minimal_pro": TemplateMeta("minimal_pro", "Minimal Pro", "subtle", "compact", ["finance", "general"], "shape"),
    "sprite_quest": TemplateMeta("sprite_quest", "Sprite Quest (Legacy)", "energetic", "narrative", ["programming", "science"], "sprite"),
}

THEMES: Dict[str, Dict[str, str]] = {
    "python_dark": {"bg": "#0f172a", "panel": "#111f38", "accent": "#ffd43b", "title": "#f8fafc", "muted": "#bfdbfe", "text": "#e2e8f0", "ground": "#64748b"},
    "science_lab": {"bg": "#081c15", "panel": "#1b4332", "accent": "#74c69d", "title": "#f1faee", "muted": "#b7e4c7", "text": "#ecfdf5", "ground": "#52796f"},
    "history_archive": {"bg": "#2b2118", "panel": "#3b2f2f", "accent": "#d4a373", "title": "#fefae0", "muted": "#faedcd", "text": "#fff8e7", "ground": "#7f5539"},
    "finance_neutral": {"bg": "#0b132b", "panel": "#1c2541", "accent": "#5bc0be", "title": "#f7fff7", "muted": "#c6f1ef", "text": "#edf6f9", "ground": "#3a506b"},
    "minimal_light": {"bg": "#e8eef5", "panel": "#ffffff", "accent": "#2563eb", "title": "#0f172a", "muted": "#334155", "text": "#1e293b", "ground": "#94a3b8"},
}

TOPIC_TEMPLATE_MAP: Dict[str, List[str]] = {
    "programming": ["player_lesson_modern", "ide_walkthrough", "concept_cards_motion", "quiz_showcase"],
    "science": ["concept_cards_motion", "quiz_showcase", "ide_walkthrough", "player_lesson_modern"],
    "history": ["cinematic_cards", "concept_cards_motion", "minimal_pro"],
    "finance": ["minimal_pro", "concept_cards_motion", "player_lesson_modern"],
    "general": ["player_lesson_modern", "concept_cards_motion", "quiz_showcase", "cinematic_cards"],
}

TOPIC_THEME_MAP: Dict[str, str] = {
    "programming": "python_dark",
    "science": "science_lab",
    "history": "history_archive",
    "finance": "finance_neutral",
    "general": "minimal_light",
}


def _normalize_facts(facts: Optional[List[dict]], text_density: TextDensity) -> List[SpriteFact]:
    limits = {"compact": 180, "balanced": 280, "detailed": 420}
    char_limit = limits[text_density]
    if not facts:
        return DEFAULT_PYTHON_FACTS
    normalized: List[SpriteFact] = []
    for raw in facts:
        if not isinstance(raw, dict):
            continue
        year = str(raw.get("year", "STEP")).strip()[:32]
        cat = str(raw.get("cat", "TOPIC")).strip()[:42]
        text = str(raw.get("text", "")).strip()
        text = re.sub(r"[ \t]+", " ", text)
        text = text[:char_limit]
        if not text:
            continue
        normalized.append({"year": year or "STEP", "cat": cat or "TOPIC", "text": text})
    return normalized[:12] if normalized else DEFAULT_PYTHON_FACTS


def _detect_topic_family(topic: str, requested: Optional[str]) -> TopicFamily:
    if requested in {"programming", "science", "history", "finance", "general"}:
        return requested  # type: ignore[return-value]
    t = topic.lower()
    if any(k in t for k in ("python", "code", "program", "javascript", "api", "software")):
        return "programming"
    if any(k in t for k in ("biology", "physics", "chemistry", "science", "cell", "dna")):
        return "science"
    if any(k in t for k in ("history", "empire", "war", "ancient", "medieval")):
        return "history"
    if any(k in t for k in ("finance", "money", "investment", "budget", "accounting")):
        return "finance"
    return "general"


def _pick_template(topic_family: TopicFamily, forced_template_id: Optional[str]) -> str:
    global _LAST_TEMPLATE_ID
    if forced_template_id in TEMPLATES:
        _LAST_TEMPLATE_ID = forced_template_id
        return forced_template_id
    candidates = TOPIC_TEMPLATE_MAP.get(topic_family, TOPIC_TEMPLATE_MAP["general"])
    if _LAST_TEMPLATE_ID in candidates and len(candidates) > 1:
        candidates = [c for c in candidates if c != _LAST_TEMPLATE_ID]
    chosen = random.choice(candidates)
    _LAST_TEMPLATE_ID = chosen
    return chosen


def _pick_theme(topic_family: TopicFamily, forced_theme_id: Optional[str]) -> str:
    if forced_theme_id in THEMES:
        return forced_theme_id
    return TOPIC_THEME_MAP.get(topic_family, "minimal_light")


def _validate_sprite_sheet(sheet: object) -> bool:
    if not isinstance(sheet, list) or len(sheet) < 2:
        return False
    for frame in sheet:
        if not isinstance(frame, list) or len(frame) < 6:
            return False
        widths = {len(row) for row in frame if isinstance(row, list)}
        if len(widths) != 1 or not widths:
            return False
    return True


def _curated_sprites(topic_family: TopicFamily) -> List[List[List[int]]]:
    python_snake = [
        [[0,0,1,1,1,0,0,0],[0,1,1,7,1,1,0,0],[1,1,7,7,7,1,1,0],[1,7,7,1,7,7,1,0],[1,1,7,7,7,1,1,0],[0,1,1,1,1,1,0,0],[0,0,3,0,0,3,0,0],[0,3,0,0,0,0,3,0]],
        [[0,0,1,1,1,0,0,0],[0,1,1,7,1,1,0,0],[1,1,7,7,7,1,1,0],[1,7,7,1,7,7,1,0],[1,1,7,7,7,1,1,0],[0,1,1,1,1,1,0,0],[0,3,0,0,0,3,0,0],[3,0,0,0,0,0,0,3]],
    ]
    science_atom = [
        [[0,0,11,11,0,0,0,0],[0,11,11,11,11,0,0,0],[11,11,7,7,11,11,0,0],[11,11,7,7,11,11,0,0],[0,11,11,11,11,0,0,0],[0,0,11,11,0,0,0,0],[0,0,0,3,0,0,0,0],[0,0,3,0,3,0,0,0]],
        [[0,0,11,11,0,0,0,0],[0,11,11,11,11,0,0,0],[11,11,7,7,11,11,0,0],[11,11,7,7,11,11,0,0],[0,11,11,11,11,0,0,0],[0,0,11,11,0,0,0,0],[0,0,3,0,3,0,0,0],[0,3,0,0,0,3,0,0]],
    ]
    history_knight = [
        [[0,0,5,5,0,0,0,0],[0,5,5,5,5,0,0,0],[0,0,2,2,0,0,0,0],[0,2,2,2,2,0,0,0],[0,9,9,9,9,0,0,0],[0,9,9,9,9,9,0,0],[0,9,9,0,9,9,0,0],[0,3,3,0,3,3,0,0]],
        [[0,0,5,5,0,0,0,0],[0,5,5,5,5,0,0,0],[0,0,2,2,0,0,0,0],[0,2,2,2,2,0,0,0],[0,9,9,9,9,0,0,0],[0,0,9,9,9,9,9,0],[0,9,9,0,0,9,0,0],[0,3,0,0,0,3,0,0]],
    ]
    finance_analyst = [
        [[0,0,5,5,5,0,0,0],[0,5,5,5,5,5,0,0],[0,0,2,2,2,0,0,0],[0,2,2,2,2,2,0,0],[0,4,4,4,4,4,0,0],[0,4,4,4,4,4,4,0],[0,4,4,0,4,4,0,0],[0,3,3,0,3,3,0,0]],
        [[0,0,5,5,5,0,0,0],[0,5,5,5,5,5,0,0],[0,0,2,2,2,0,0,0],[0,2,2,2,2,2,0,0],[0,4,4,4,4,4,0,0],[0,0,4,4,4,4,4,0],[0,4,4,0,0,4,0,0],[0,3,0,0,0,3,0,0]],
    ]
    return {
        "programming": python_snake,
        "science": science_atom,
        "history": history_knight,
        "finance": finance_analyst,
        "general": python_snake,
    }[topic_family]


def _generate_ai_sprite_sheet(topic: str, topic_family: TopicFamily) -> Optional[List[List[List[int]]]]:
    # Lightweight optional path: enable via env var, keep deterministic fallback.
    if os.getenv("SUDARVID_ENABLE_AI_SPRITES", "0").lower() not in {"1", "true", "yes"}:
        return None
    base = _curated_sprites(topic_family)
    # Simulate style variation for topic personalization.
    shift = max(1, len(topic) % 3)
    generated: List[List[List[int]]] = []
    for frame in base:
        new_frame: List[List[int]] = []
        for row in frame:
            new_row = [((px + shift) if px in (1, 4, 9, 11) else px) for px in row]
            new_frame.append(new_row)
        generated.append(new_frame)
    return generated if _validate_sprite_sheet(generated) else None


def _select_sprites(topic: str, topic_family: TopicFamily, sprite_mode: SpriteMode) -> List[List[List[int]]]:
    curated = _curated_sprites(topic_family)
    if sprite_mode == "library_only":
        return curated
    generated = _generate_ai_sprite_sheet(topic, topic_family)
    if sprite_mode == "ai_preferred" and generated is not None:
        return generated
    if sprite_mode == "auto" and generated is not None:
        return generated
    return curated


def list_sprite_templates() -> List[dict]:
    return [
        {
            "id": t.id,
            "label": t.label,
            "motion_profile": t.motion_profile,
            "text_profile": t.text_profile,
            "preferred_topics": t.preferred_topics,
            "asset_mode": t.asset_mode,
        }
        for t in TEMPLATES.values()
    ]


def list_sprite_themes() -> List[dict]:
    return [{"id": k, **v} for k, v in THEMES.items()]


def _build_common_script(payload: RenderPayload, include_canvas: bool) -> str:
    typing_ms = {"compact": 14, "balanced": 18, "detailed": 22}[payload["text_density"]]
    motion_mult = {"low": 0.65, "medium": 1.0, "high": 1.35}[payload["motion_level"]]
    base = {
        "facts": payload["facts"],
        "scoreLabel": payload["score_label"],
        "templateId": payload["template_id"],
        "typingMs": typing_ms,
        "motionMult": motion_mult,
        "sprites": payload["sprites"],
    }
    return f"""
<script>
const LESSON = {json.dumps(base, ensure_ascii=False)};
let idx = 0, autoTmr = null, score = 0, typingTimer = null, rafId = null, tick = 0;
let deckClock = 0;
let playing = true;
const facts = LESSON.facts;
const factLabel = document.getElementById("factLabel");
const factMeta = document.getElementById("factMeta");
const factText = document.getElementById("factText");
const progress = document.getElementById("progressFill");
const scoreDisp = document.getElementById("scoreDisp");
const dots = document.getElementById("dots");
const screen = document.getElementById("screen");
const playBtn = document.getElementById("playBtn");
const timeline = document.getElementById("timeline");
const timelineFill = document.getElementById("timelineFill");
const timeLabel = document.getElementById("timeLabel");
const chapterRow = document.getElementById("chapterRow");
const quizPanel = document.getElementById("quizPanel");
const quizPrompt = document.getElementById("quizPrompt");
const quizChoices = document.getElementById("quizChoices");
const quizFeedback = document.getElementById("quizFeedback");

function stopTyping() {{
  if (typingTimer) {{
    clearInterval(typingTimer);
    typingTimer = null;
  }}
}}

function typeText(text) {{
  stopTyping();
  factText.textContent = "";
  let i = 0;
  typingTimer = setInterval(() => {{
    if (i >= text.length) {{
      stopTyping();
      return;
    }}
    const ch = text[i];
    if (ch === "\\n") {{
      factText.appendChild(document.createElement("br"));
    }} else {{
      factText.appendChild(document.createTextNode(ch));
    }}
    i += 1;
  }}, LESSON.typingMs);
}}

function fmtTime(sec) {{
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m + ":" + String(r).padStart(2, "0");
}}

function updateTimeline() {{
  const total = facts.length * 7;
  const p = Math.min(1, deckClock / total);
  if (timelineFill) timelineFill.style.width = (p * 100).toFixed(2) + "%";
  if (timeLabel) timeLabel.textContent = fmtTime(deckClock) + " / " + fmtTime(total);
}}

function buildChapters() {{
  if (!chapterRow) return;
  chapterRow.innerHTML = "";
  facts.forEach((f, i) => {{
    const c = document.createElement("button");
    c.className = "chapterBtn";
    c.textContent = f.year;
    c.onclick = () => {{
      idx = i;
      deckClock = i * 7;
      show(0);
      updateTimeline();
      resetTimer();
    }};
    chapterRow.appendChild(c);
  }});
}}

function setupQuizForFact(f) {{
  if (!quizPanel || !quizPrompt || !quizChoices || !quizFeedback) return;
  if (LESSON.templateId !== "quiz_showcase") {{
    quizPanel.style.display = "none";
    return;
  }}
  quizPanel.style.display = "block";
  quizPrompt.textContent = "Quick check: Which statement best matches this chapter?";
  const choices = [
    f.text.split("\\n")[0].slice(0, 72),
    "Python ignores indentation and formatting rules.",
    "Variables cannot store words or numbers."
  ];
  const correct = 0;
  quizChoices.innerHTML = "";
  quizFeedback.textContent = "";
  choices.forEach((label, i) => {{
    const b = document.createElement("button");
    b.className = "quizChoice";
    b.textContent = label;
    b.onclick = () => {{
      if (i === correct) {{
        quizFeedback.textContent = "Correct - great understanding.";
        quizFeedback.className = "quizFeedback good";
      }} else {{
        quizFeedback.textContent = "Not quite - review this chapter and try again.";
        quizFeedback.className = "quizFeedback bad";
      }}
    }};
    quizChoices.appendChild(b);
  }});
}}

function makeDots() {{
  dots.innerHTML = "";
  facts.forEach((_, i) => {{
    const d = document.createElement("button");
    d.className = "dotBtn";
    d.setAttribute("aria-label", "Go to lesson " + (i + 1));
    if (i === idx) d.classList.add("active");
    d.onclick = () => {{
      idx = i;
      show(0);
      resetTimer();
    }};
    dots.appendChild(d);
  }});
}}

function show(dir) {{
  const f = facts[idx];
  screen.style.opacity = "0";
  screen.style.transform = "translateY(" + (dir >= 0 ? "8px" : "-8px") + ")";
  setTimeout(() => {{
    factLabel.textContent = "LESSON " + String(idx + 1).padStart(2, "0") + " / " + facts.length;
    factMeta.textContent = f.year + " — " + f.cat;
    typeText(f.text);
    progress.style.width = ((idx + 1) / facts.length * 100) + "%";
    score += 1;
    scoreDisp.textContent = LESSON.scoreLabel + " × " + String(score).padStart(2, "0");
    setupQuizForFact(f);
    makeDots();
    screen.style.opacity = "1";
    screen.style.transform = "translateY(0)";
  }}, 220);
}}

function go(delta) {{
  idx = (idx + delta + facts.length) % facts.length;
  show(delta);
  resetTimer();
}}

function resetTimer() {{
  clearInterval(autoTmr);
  autoTmr = setInterval(() => {{
    if (!playing) return;
    deckClock += 1;
    updateTimeline();
    if (deckClock % 7 === 0) go(1);
  }}, 1000);
}}

if (playBtn) {{
  playBtn.onclick = () => {{
    playing = !playing;
    playBtn.textContent = playing ? "Pause" : "Play";
  }};
}}

if (timeline) {{
  timeline.onclick = (ev) => {{
    const r = timeline.getBoundingClientRect();
    const x = Math.max(0, Math.min(r.width, ev.clientX - r.left));
    const ratio = r.width > 0 ? x / r.width : 0;
    const total = facts.length * 7;
    deckClock = ratio * total;
    idx = Math.min(facts.length - 1, Math.floor(deckClock / 7));
    show(0);
    updateTimeline();
    resetTimer();
  }};
}}

window.goLesson = go;
buildChapters();
makeDots();
show(0);
updateTimeline();
resetTimer();
{_canvas_script() if include_canvas else ""}
</script>
"""


def _canvas_script() -> str:
    return """
const canvas = document.getElementById("worldCanvas");
if (canvas) {
  const cx = canvas.getContext("2d");
  const GY = 62, S = 3;
  const sprite = LESSON.sprites;
  const walkers = [
    { x: 80, y: GY - 8*S, fr: 0, tk: 0, speed: 0.9 * LESSON.motionMult },
    { x: 330, y: GY - 8*S, fr: 1, tk: 0, speed: 0.7 * LESSON.motionMult },
    { x: 560, y: GY - 8*S, fr: 0, tk: 0, speed: 1.2 * LESSON.motionMult },
  ];
  const clouds = [{x:40,y:9,w:66,h:14},{x:280,y:11,w:84,h:16},{x:500,y:7,w:48,h:12}];

  const palette = {0:"transparent",1:"#306998",2:"#ffcc99",3:"#7a4b2e",4:"#4a90e2",5:"#ffffff",6:"#111111",7:"#ffd43b",8:"#2ea836",9:"#ff8c00",10:"#1f4c74",11:"#66d9ef",12:"#b6f8ff",13:"#7c3aed",14:"#f97316"};
  function drawPx(frame, px, py, scale) {
    for (let r = 0; r < frame.length; r++) {
      for (let c = 0; c < frame[r].length; c++) {
        const ci = frame[r][c];
        if (!ci) continue;
        cx.fillStyle = palette[ci] || "#fff";
        cx.fillRect(Math.round(px + c * scale), Math.round(py + r * scale), scale, scale);
      }
    }
  }

  function render() {
    cx.clearRect(0,0,680,94);
    cx.fillStyle = "#0b1f3a"; cx.fillRect(0,0,680,94);
    clouds.forEach((c) => {
      c.x -= 0.14 * LESSON.motionMult; if (c.x < -100) c.x = 710;
      cx.fillStyle = "#bfd7ff"; cx.fillRect(Math.round(c.x), c.y, c.w, c.h);
      cx.fillRect(Math.round(c.x + 8), c.y - 4, c.w - 16, 7);
    });
    cx.fillStyle = "#4b9f2c"; cx.fillRect(0,GY,680,5);
    cx.fillStyle = "#6a4b17"; cx.fillRect(0,GY+5,680,30);
    cx.strokeStyle = "rgba(0,0,0,0.18)";
    for (let x=0; x<680; x+=22) cx.strokeRect(x, GY+5, 22, 30);
    cx.fillStyle = tick % 40 < 20 ? "#ffd43b" : "#eab308";
    cx.fillRect(244, GY-28, 16, 16); cx.fillRect(266, GY-28, 16, 16);
    cx.fillStyle = "#6b3800"; cx.font = "bold 10px monospace"; cx.fillText("?", 249, GY-16); cx.fillText("{", 271, GY-16);

    walkers.forEach((w, i) => {
      w.tk += 1;
      if (w.tk % (10 + i * 3) === 0) w.fr = (w.fr + 1) % sprite.length;
      w.x -= w.speed;
      if (w.x < -60) w.x = 710;
      drawPx(sprite[w.fr], w.x, w.y, S);
    });
    tick += 1;
    rafId = requestAnimationFrame(render);
  }
  render();
}
"""


def _container_css(theme: Dict[str, str], template_id: str) -> str:
    return f"""
<style>
:root {{
  --bg:{theme["bg"]};
  --panel:{theme["panel"]};
  --accent:{theme["accent"]};
  --title:{theme["title"]};
  --muted:{theme["muted"]};
  --text:{theme["text"]};
  --ground:{theme["ground"]};
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 24px 14px;
  background: var(--bg);
  font-family: Inter, "Segoe UI", Roboto, Arial, sans-serif;
  color: var(--text);
}}
.lessonRoot {{
  width: min(980px, 96vw);
  margin: 0 auto;
  border: 3px solid #0b0b0b;
  border-radius: 14px;
  overflow: hidden;
  background: var(--panel);
}}
.topBar {{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:10px;
  background: color-mix(in srgb, var(--panel) 60%, #000 40%);
  border-bottom: 2px solid #000;
  padding: 10px 16px;
}}
.title {{
  color: var(--title);
  font-weight: 700;
  letter-spacing: 2px;
  font-size: 15px;
}}
.score {{
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
}}
#screen {{
  min-height: 230px;
  padding: 24px 26px 20px;
  position: relative;
  transition: opacity .24s ease, transform .24s ease;
  background: linear-gradient(135deg, color-mix(in srgb, var(--bg) 82%, black 18%), color-mix(in srgb, var(--panel) 78%, black 22%));
}}
.factLabel {{
  text-align:center;
  color: var(--accent);
  letter-spacing: 3px;
  font-size: 10px;
  font-weight: 700;
  margin-bottom: 10px;
}}
.factMeta {{
  text-align:center;
  margin: 0 auto 12px;
  font-size: 11px;
  border: 1px solid color-mix(in srgb, var(--accent) 60%, transparent);
  border-radius: 6px;
  display:inline-block;
  padding: 4px 12px;
  letter-spacing: 1.4px;
}}
.metaWrap {{ text-align:center; }}
.objective {{
  text-align:center;
  color: var(--muted);
  font-size: 12px;
  max-width: 760px;
  margin: 0 auto 10px;
  line-height: 1.45;
}}
.factText {{
  text-align:center;
  max-width: 760px;
  margin: 0 auto;
  min-height: 90px;
  line-height: 1.7;
  font-size: clamp(14px, 1.7vw, 18px);
  letter-spacing: 0.2px;
  word-break: normal;
  overflow-wrap: anywhere;
  white-space: normal;
  text-wrap: pretty;
}}
.progressTrack {{ height: 4px; background: color-mix(in srgb, var(--panel) 45%, #000 55%); }}
.progressFill {{ height: 100%; background: var(--accent); width: 8%; transition: width .35s ease; }}
.worldRow {{ background: color-mix(in srgb, var(--panel) 58%, #000 42%); border-top: 1px solid #000; }}
.controls {{
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding: 8px 14px 10px;
  background: color-mix(in srgb, var(--panel) 65%, #000 35%);
  border-top: 2px solid #000;
  flex-wrap: wrap;
  gap: 8px;
}}
.ctlBtn {{
  color: var(--title);
  background: color-mix(in srgb, var(--panel) 48%, #000 52%);
  border: 2px solid color-mix(in srgb, var(--title) 70%, transparent);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 6px 16px;
  cursor: pointer;
}}
.dotWrap {{ display:flex; gap:7px; align-items:center; justify-content:center; }}
.playerUi {{
  border-top: 1px solid color-mix(in srgb, var(--title) 25%, transparent);
  padding: 10px 14px;
  background: color-mix(in srgb, var(--panel) 72%, #000 28%);
}}
.playerTop {{
  display:flex;
  gap:10px;
  align-items:center;
  justify-content:space-between;
}}
.timeline {{
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--title) 22%, transparent);
  overflow: hidden;
  cursor: pointer;
}}
.timelineFill {{
  height: 100%;
  width: 0;
  background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 70%, #fff 30%));
}}
.timeLabel {{
  font-size: 12px;
  min-width: 84px;
  text-align: right;
  color: var(--muted);
}}
.chapterRow {{
  display:flex;
  gap:8px;
  flex-wrap: wrap;
  margin-top: 10px;
}}
.chapterBtn {{
  border: 1px solid color-mix(in srgb, var(--title) 35%, transparent);
  background: color-mix(in srgb, var(--panel) 35%, #000 65%);
  color: var(--muted);
  font-size: 11px;
  border-radius: 999px;
  padding: 3px 10px;
  cursor: pointer;
}}
.quizPanel {{
  margin: 12px auto 0;
  max-width: 760px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--title) 22%, transparent);
  background: color-mix(in srgb, var(--panel) 78%, #000 22%);
}}
.quizPrompt {{
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
}}
.quizChoices {{
  display:grid;
  gap: 8px;
}}
.quizChoice {{
  text-align: left;
  border: 1px solid color-mix(in srgb, var(--title) 35%, transparent);
  border-radius: 8px;
  padding: 8px 10px;
  background: color-mix(in srgb, var(--panel) 45%, #000 55%);
  color: var(--text);
  cursor: pointer;
}}
.quizFeedback {{
  margin-top: 10px;
  font-size: 12px;
  color: var(--muted);
}}
.quizFeedback.good {{ color: #86efac; }}
.quizFeedback.bad {{ color: #fca5a5; }}
.dotBtn {{
  width:8px;height:8px;border-radius:50%;
  border: 1px solid color-mix(in srgb, var(--title) 45%, transparent);
  background: color-mix(in srgb, var(--title) 20%, transparent);
  cursor:pointer;
}}
.dotBtn.active {{ background: var(--title); }}
canvas {{ display:block; width:100%; height:auto; }}
body.template-cinematic_cards #screen {{ background: radial-gradient(circle at 30% 20%, color-mix(in srgb, var(--accent) 20%, transparent), transparent 45%), linear-gradient(160deg, var(--bg), var(--panel)); }}
body.template-ide_walkthrough .factText {{
  text-align: left;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  background: color-mix(in srgb, var(--bg) 84%, #000 16%);
  border: 1px solid color-mix(in srgb, var(--title) 25%, transparent);
  border-radius: 10px;
  padding: 12px 14px;
}}
body.template-player_lesson_modern #screen {{ background: linear-gradient(145deg, #151d32, #0e162a); }}
body.template-minimal_pro .factText {{ max-width: 700px; font-size: clamp(14px, 1.35vw, 16px); }}
body.template-concept_cards_motion .factText::before {{ content: "• "; color: var(--accent); }}
body.template-quiz_showcase #screen {{ background: linear-gradient(150deg, #101b35, #172554); }}
@media (max-width: 820px) {{
  .title {{ font-size: 13px; letter-spacing: 1px; }}
  .factText {{ min-height: 108px; line-height: 1.62; }}
  #screen {{ padding: 18px 14px; }}
  .playerTop {{ flex-wrap: wrap; }}
  .timeLabel {{ min-width: 0; width: 100%; text-align: left; }}
}}
</style>
"""


def _render_template(payload: RenderPayload) -> str:
    include_canvas = payload["template_id"] == "sprite_quest"
    objective_html = f"<p class=\"objective\"><strong>OBJECTIVE:</strong> {payload['objective']}</p>" if payload["objective"] else ""
    world_html = "<div class=\"worldRow\"><canvas id=\"worldCanvas\" width=\"680\" height=\"94\"></canvas></div>" if include_canvas else ""
    template_label = TEMPLATES[payload["template_id"]].label.upper()
    header = f"★ {payload['topic'].upper()} — {template_label} ★"
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{payload["topic"]}</title>
{_container_css(THEMES[payload["theme_id"]], payload["template_id"])}
</head>
<body class="template-{payload["template_id"]}">
  <h2 class="sr-only">Dynamic lesson for {payload["topic"]}</h2>
  <div class="lessonRoot">
    <div class="topBar">
      <div class="title">{header}</div>
      <div class="score" id="scoreDisp">{payload["score_label"]} × 00</div>
    </div>
    <section id="screen">
      <div class="factLabel" id="factLabel">LESSON 01 / {len(payload["facts"])}</div>
      <div class="metaWrap"><div class="factMeta" id="factMeta">START — INTRO</div></div>
      {objective_html}
      <div class="factText" id="factText"></div>
      <div class="quizPanel" id="quizPanel" style="display:none;">
        <div class="quizPrompt" id="quizPrompt"></div>
        <div class="quizChoices" id="quizChoices"></div>
        <div class="quizFeedback" id="quizFeedback"></div>
      </div>
    </section>
    <div class="progressTrack"><div class="progressFill" id="progressFill"></div></div>
    <div class="playerUi">
      <div class="playerTop">
        <button class="ctlBtn" id="playBtn">Pause</button>
        <div class="timeline" id="timeline"><div class="timelineFill" id="timelineFill"></div></div>
        <div class="timeLabel" id="timeLabel">0:00 / 0:00</div>
      </div>
      <div class="chapterRow" id="chapterRow"></div>
    </div>
    {world_html}
    <div class="controls">
      <button class="ctlBtn" onclick="goLesson(-1)">◀ BACK</button>
      <div class="dotWrap" id="dots"></div>
      <button class="ctlBtn" onclick="goLesson(1)">NEXT ▶</button>
    </div>
  </div>
  {_build_common_script(payload, include_canvas=include_canvas)}
</body>
</html>"""


def render_sprite_lesson_html(
    topic: str,
    objective: Optional[str] = None,
    facts: Optional[List[dict]] = None,
    score_label: str = "XP",
    template_id: Optional[str] = None,
    theme_id: Optional[str] = None,
    topic_family: Optional[str] = None,
    sprite_mode: SpriteMode = "auto",
    motion_level: MotionLevel = "medium",
    text_density: TextDensity = "balanced",
) -> str:
    safe_topic = (topic or "Interactive Lesson").strip()[:72]
    safe_objective = (objective or "").strip()[:280]
    safe_score_label = (score_label or "XP").strip()[:16].upper()
    density = text_density if text_density in {"compact", "balanced", "detailed"} else "balanced"
    motion = motion_level if motion_level in {"low", "medium", "high"} else "medium"
    mode = sprite_mode if sprite_mode in {"auto", "library_only", "ai_preferred"} else "auto"

    family = _detect_topic_family(safe_topic, topic_family)
    selected_template = _pick_template(family, template_id)
    selected_theme = _pick_theme(family, theme_id)
    normalized_facts = _normalize_facts(facts, density)
    sprites = _select_sprites(safe_topic, family, mode)

    payload: RenderPayload = {
        "topic": safe_topic,
        "objective": safe_objective,
        "score_label": safe_score_label,
        "facts": normalized_facts,
        "theme_id": selected_theme,
        "template_id": selected_template,
        "motion_level": motion,  # type: ignore[assignment]
        "text_density": density,  # type: ignore[assignment]
        "sprite_mode": mode,  # type: ignore[assignment]
        "topic_family": family,
        "sprites": sprites,
    }
    return _render_template(payload)
