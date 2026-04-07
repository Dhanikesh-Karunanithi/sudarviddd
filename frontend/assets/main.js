const app = document.getElementById("app");

/** @type {{ topic: string, audience: string, length: string, theme: string } | null} */
let lastJobPrefs = null;
let lastAttemptedJobId = "";

function isPreviewRoute() {
  return window.location.pathname.startsWith("/v/");
}

function getPreviewJobId() {
  const parts = window.location.pathname.split("/");
  const raw = parts[2] || "";
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

function swatchColor(theme, key) {
  return (
    theme?.colors?.[key] ||
    theme?.[key] ||
    (theme?.palette ? theme.palette[key] : null) ||
    "#222"
  );
}

/** @param {string} fontStack */
function cssFontStack(fontStack) {
  if (!fontStack || typeof fontStack !== "string") return "system-ui, sans-serif";
  return fontStack.replace(/"/g, "'").trim();
}

function lengthPreset(id) {
  const map = {
    short: { target_duration_seconds: 120, slide_count: 5 },
    medium: { target_duration_seconds: 300, slide_count: 8 },
    long: { target_duration_seconds: 600, slide_count: 12 }
  };
  return map[id] || map.medium;
}

function audienceLabel(id) {
  const map = {
    beginner: "beginners",
    intermediate: "intermediate learners",
    expert: "expert audience"
  };
  return map[id] || "general audience";
}

/** Mood bucket for theme grid sections */
const THEME_MOOD = {
  modern_newspaper: "professional",
  sharp_minimalism: "professional",
  yellow_black: "bold",
  black_orange: "bold",
  manga: "creative",
  magazine: "creative",
  neo_retro_dev: "creative",
  pink_street: "bold",
  mincho_handwritten: "creative",
  seminar_minimal: "professional",
  royal_blue_red: "professional",
  studio_premium: "professional",
  sports: "bold",
  classic_pop: "bold",
  tech_neon: "creative",
  digital_neo_pop: "creative",
  anti_gravity: "professional",
  deformed_persona: "creative"
};

const MOOD_ORDER = [
  { id: "professional", label: "Professional" },
  { id: "creative", label: "Creative" },
  { id: "bold", label: "Bold" }
];

function renderPreview(jobId) {
  app.innerHTML = `
    <div class="container">
      <div style="margin-bottom:10px;"><a href="/">← Back</a></div>
      <div class="preview-layout">
        <div class="card">
          <h3 style="margin-top:0;">Preview</h3>
          <iframe src="/render/${encodeURIComponent(jobId)}/slides.html"></iframe>
        </div>
        <div class="card">
          <h3 style="margin-top:0;">Downloads</h3>
          <p><a href="/export/${encodeURIComponent(jobId)}/bundle.zip">Download full bundle (.zip)</a></p>
          <p><a href="/download/${encodeURIComponent(jobId)}/slides.html">slides.html</a></p>
          <p><a href="/download/${encodeURIComponent(jobId)}/audio/voiceover.mp3">voiceover.mp3</a></p>
          <p><a href="/download/${encodeURIComponent(jobId)}/video/output.mp4">output.mp4</a></p>
          <p class="muted">If a file is missing, it was not generated for this job.</p>
        </div>
      </div>
    </div>
  `;
}

function buildThemeCard(t, selectedId) {
  const bg = swatchColor(t, "bg");
  const accent = swatchColor(t, "accent");
  const secondary = swatchColor(t, "secondary");
  const text = t.text_color || "#111111";
  const bulletGrey =
    text.startsWith("#") && text.length >= 7
      ? `${text}55`
      : "rgba(0,0,0,0.25)";
  const font = cssFontStack(t.font_heading);
  const gradId = `miniGrad_${t.id.replace(/[^a-z0-9]/gi, "_")}`;
  const shortPreview = "Preview";

  return `
    <button type="button" class="theme-preview-card${t.id === selectedId ? " selected" : ""}" data-theme-id="${t.id}"
      style="--preview-font: ${font}, system-ui, sans-serif" aria-pressed="${t.id === selectedId}">
      <div class="theme-mini-wrap">
        <div class="theme-mini-slide" style="background-color:${bg};color:${text}">
          <svg class="theme-mini-bg" viewBox="0 0 240 135" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <defs>
              <linearGradient id="${gradId}" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#000" stop-opacity="0.28"/>
                <stop offset="100%" stop-color="#000" stop-opacity="0.06"/>
              </linearGradient>
            </defs>
            <rect width="240" height="135" fill="url(#${gradId})"/>
          </svg>
          <div class="theme-mini-inner">
            <div class="theme-mini-title">${escapeHtml(shortPreview)}</div>
            <div class="theme-mini-accent" style="background:${accent}"></div>
            <div class="theme-mini-bullets">
              <span style="background:${bulletGrey}"></span>
              <span style="background:${bulletGrey}"></span>
            </div>
          </div>
        </div>
        <div class="theme-thumb-overlay" title="${escapeHtml(t.label)}">
          <span class="theme-thumb-overlay-text">${escapeHtml(t.label)}</span>
        </div>
      </div>
      <div class="theme-swatches" aria-hidden="true">
        <span class="swatch" style="background:${bg}" title="Background"></span>
        <span class="swatch" style="background:${accent}" title="Accent"></span>
        <span class="swatch" style="background:${secondary}" title="Secondary"></span>
      </div>
    </button>
  `;
}

function groupThemesByMood(themes) {
  /** @type {Record<string, typeof themes>} */
  const buckets = { professional: [], creative: [], bold: [] };
  for (const t of themes) {
    const m = THEME_MOOD[t.id] || "creative";
    (buckets[m] || buckets.creative).push(t);
  }
  return buckets;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/** Canvas loader animation (see sudar_loading_v3.html in repo root) */
const SUDAR_LOADER_W = 300;
const SUDAR_LOADER_H = 200;
const SL_MX = SUDAR_LOADER_W / 2;
const SL_MY = SUDAR_LOADER_H / 2;

let sudarLoaderRafId = null;
let sudarLoaderT0 = null;

function slEaseInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}
function slEaseInOutQuint(t) {
  return t < 0.5 ? 16 * t * t * t * t * t : 1 - Math.pow(-2 * t + 2, 5) / 2;
}
function slLerp(a, b, t) {
  return a + (b - a) * t;
}
function slClamp(t) {
  return Math.max(0, Math.min(1, t));
}

/** @param {CanvasRenderingContext2D} cx */
function slDrawPill(cx, px, py, pw, ph, pr, pa, withShadow) {
  if (pa <= 0.004) return;
  cx.save();
  cx.globalAlpha = pa;
  if (withShadow) {
    cx.shadowColor = "rgba(0,0,0,0.45)";
    cx.shadowBlur = 28;
    cx.shadowOffsetY = 10;
  }
  cx.translate(px, py);
  const r = Math.min(pr, pw / 2, ph / 2);
  const x = -pw / 2;
  const y = -ph / 2;
  cx.beginPath();
  cx.moveTo(x + r, y);
  cx.lineTo(x + pw - r, y);
  cx.arcTo(x + pw, y, x + pw, y + r, r);
  cx.lineTo(x + pw, y + ph - r);
  cx.arcTo(x + pw, y + ph, x + pw - r, y + ph, r);
  cx.lineTo(x + r, y + ph);
  cx.arcTo(x, y + ph, x, y + ph - r, r);
  cx.lineTo(x, y + r);
  cx.arcTo(x, y, x + r, y, r);
  cx.closePath();
  cx.fillStyle = "#f5f5f5";
  cx.fill();
  cx.restore();
}

/** @param {CanvasRenderingContext2D} cx */
function slDrawAIStar(cx, sx, sy, sz, sa) {
  if (sa <= 0.004) return;
  cx.save();
  cx.globalAlpha = sa;
  cx.translate(sx, sy);
  cx.shadowColor = "rgba(255,255,255,0.2)";
  cx.shadowBlur = 8;
  const r = sz;
  const c = r * 0.12;
  cx.beginPath();
  cx.moveTo(0, -r);
  cx.bezierCurveTo(c, -c, c, -c, r, 0);
  cx.bezierCurveTo(c, c, c, c, 0, r);
  cx.bezierCurveTo(-c, c, -c, c, -r, 0);
  cx.bezierCurveTo(-c, -c, -c, -c, 0, -r);
  cx.closePath();
  cx.fillStyle = "#000000";
  cx.fill();
  cx.restore();
}

/** @param {CanvasRenderingContext2D} cx */
function slDrawPlay(cx, px, py, sz, pa) {
  if (pa <= 0.004) return;
  cx.save();
  cx.globalAlpha = pa;
  cx.translate(px, py);
  cx.beginPath();
  cx.moveTo(-sz * 0.36, -sz * 0.5);
  cx.lineTo(sz * 0.62, 0);
  cx.lineTo(-sz * 0.36, sz * 0.5);
  cx.closePath();
  cx.fillStyle = "#000000";
  cx.fill();
  cx.restore();
}

const SL_KF = {
  s1: {
    p1: { x: SL_MX + 22, y: SL_MY - 28, w: 138, h: 55, rx: 27.5, a: 1 },
    p2: { x: SL_MX - 22, y: SL_MY + 28, w: 138, h: 55, rx: 27.5, a: 1 },
    star: { sz: 16, a: 1 },
    play: { sz: 24, a: 0 }
  },
  s2: {
    p1: { x: SL_MX, y: SL_MY - 19, w: 138, h: 55, rx: 27.5, a: 1 },
    p2: { x: SL_MX, y: SL_MY + 19, w: 138, h: 55, rx: 27.5, a: 1 },
    star: { sz: 16, a: 1 },
    play: { sz: 24, a: 0 }
  },
  s3: {
    p1: { x: SL_MX, y: SL_MY, w: 152, h: 82, rx: 41, a: 1 },
    p2: { x: SL_MX, y: SL_MY, w: 152, h: 82, rx: 41, a: 0 },
    star: { sz: 16, a: 1 },
    play: { sz: 24, a: 0 }
  },
  s4: {
    p1: { x: SL_MX, y: SL_MY, w: 162, h: 100, rx: 20, a: 1 },
    p2: { x: SL_MX, y: SL_MY, w: 162, h: 100, rx: 20, a: 0 },
    star: { sz: 16, a: 0 },
    play: { sz: 24, a: 1 }
  }
};

function slInterpKF(A, B, t, posE, szE) {
  posE = posE || slEaseInOutCubic;
  szE = szE || slEaseInOutCubic;
  const pe = posE(slClamp(t));
  const se = szE(slClamp(t));
  const ae = slEaseInOutCubic(slClamp(t));
  const lp = (a, b, e) => slLerp(a, b, e);
  return {
    p1: {
      x: lp(A.p1.x, B.p1.x, pe),
      y: lp(A.p1.y, B.p1.y, pe),
      w: lp(A.p1.w, B.p1.w, se),
      h: lp(A.p1.h, B.p1.h, se),
      rx: lp(A.p1.rx, B.p1.rx, se),
      a: lp(A.p1.a, B.p1.a, ae)
    },
    p2: {
      x: lp(A.p2.x, B.p2.x, pe),
      y: lp(A.p2.y, B.p2.y, pe),
      w: lp(A.p2.w, B.p2.w, se),
      h: lp(A.p2.h, B.p2.h, se),
      rx: lp(A.p2.rx, B.p2.rx, se),
      a: lp(A.p2.a, B.p2.a, ae)
    },
    star: { sz: lp(A.star.sz, B.star.sz, se), a: lp(A.star.a, B.star.a, ae) },
    play: { sz: lp(A.play.sz, B.play.sz, se), a: lp(A.play.a, B.play.a, ae) }
  };
}

const SL_LOOP = 6400;
const SL_TL = [
  { s: 0, e: 750, f: "s1", t: "s1", pe: slEaseInOutCubic, se: slEaseInOutCubic },
  { s: 750, e: 1450, f: "s1", t: "s2", pe: slEaseInOutQuint, se: slEaseInOutQuint },
  { s: 1450, e: 1950, f: "s2", t: "s2", pe: slEaseInOutCubic, se: slEaseInOutCubic },
  { s: 1950, e: 2650, f: "s2", t: "s3", pe: slEaseInOutQuint, se: slEaseInOutQuint },
  { s: 2650, e: 3150, f: "s3", t: "s3", pe: slEaseInOutCubic, se: slEaseInOutCubic },
  { s: 3150, e: 3850, f: "s3", t: "s4", pe: slEaseInOutQuint, se: slEaseInOutQuint },
  { s: 3850, e: 4650, f: "s4", t: "s4", pe: slEaseInOutCubic, se: slEaseInOutCubic },
  { s: 4650, e: 5250, f: "s4", t: "s3", pe: slEaseInOutQuint, se: slEaseInOutQuint },
  { s: 5250, e: 5750, f: "s3", t: "s2", pe: slEaseInOutQuint, se: slEaseInOutQuint },
  { s: 5750, e: 6400, f: "s2", t: "s1", pe: slEaseInOutQuint, se: slEaseInOutQuint }
];

function stopSudarLoader() {
  if (sudarLoaderRafId != null) {
    cancelAnimationFrame(sudarLoaderRafId);
    sudarLoaderRafId = null;
  }
  sudarLoaderT0 = null;
}

/** @param {HTMLCanvasElement} cv */
function startSudarLoader(cv) {
  stopSudarLoader();
  const cx = cv.getContext("2d");
  if (!cx) return;

  function frame(ts) {
    if (sudarLoaderT0 == null) sudarLoaderT0 = ts;
    const ms = (ts - sudarLoaderT0) % SL_LOOP;

    let seg = SL_TL[SL_TL.length - 1];
    for (const s of SL_TL) {
      if (ms >= s.s && ms < s.e) {
        seg = s;
        break;
      }
    }
    const prog = slClamp((ms - seg.s) / (seg.e - seg.s));
    const st = slInterpKF(SL_KF[seg.f], SL_KF[seg.t], prog, seg.pe, seg.se);

    const bobX = 1.6 * Math.sin(ts * 0.00175);
    const bobY = 1.4 * Math.cos(ts * 0.00155);

    cx.clearRect(0, 0, SUDAR_LOADER_W, SUDAR_LOADER_H);

    slDrawPill(cx, st.p2.x, st.p2.y, st.p2.w, st.p2.h, st.p2.rx, st.p2.a, true);
    slDrawPill(cx, st.p1.x, st.p1.y, st.p1.w, st.p1.h, st.p1.rx, st.p1.a, false);
    slDrawAIStar(cx, SL_MX + bobX, SL_MY + bobY, st.star.sz, st.star.a);
    slDrawPlay(cx, SL_MX, SL_MY, st.play.sz, st.play.a);

    sudarLoaderRafId = requestAnimationFrame(frame);
  }
  sudarLoaderRafId = requestAnimationFrame(frame);
}

function setLoading(overlay, active, text, pct) {
  if (!overlay) return;
  // Move the shared progress UI into the overlay during loading,
  // so we don't waste space (and don't show duplicate progress indicators).
  const cardId = overlay.dataset.progressCardId;
  const returnId = overlay.dataset.progressCardReturnId;
  const card = cardId ? document.getElementById(cardId) : null;
  const slot = overlay.querySelector(".loading-progress-slot");
  const returnHolder = returnId ? document.getElementById(returnId) : null;

  if (active) {
    // Hide the original container while the card is moved into the overlay.
    if (returnHolder) returnHolder.hidden = true;
    if (card && slot && card.parentElement !== slot) slot.appendChild(card);
  } else {
    if (card && returnHolder && card.parentElement !== returnHolder) {
      returnHolder.appendChild(card);
    }
    // Only reveal the main-page container when there's something to show
    // (error/warning). Otherwise keep it hidden to save layout space.
    if (returnHolder && card) {
      const errorEl = card.querySelector("#errorCard");
      const warnEl = card.querySelector("#warnCard");
      const shouldShow = (errorEl && !errorEl.hidden) || (warnEl && warnEl && !warnEl.hidden);
      if (shouldShow) returnHolder.hidden = false;
    }
  }

  const wasActive = !overlay.hidden;
  overlay.hidden = !active;
  const canvas = overlay.querySelector(".loading-canvas");
  if (canvas) {
    if (active) {
      if (!wasActive) startSudarLoader(canvas);
    } else {
      stopSudarLoader();
    }
  }
  const statusEl = overlay.querySelector(".loading-status");
  const bar = overlay.querySelector(".loading-bar-fill");
  if (statusEl && text != null) statusEl.textContent = text;
  if (bar != null && pct != null) bar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
}

/** @param {"pending"|"active"|"done"} state */
function setStepEl(el, state) {
  if (!el) return;
  el.classList.remove("is-pending", "is-active", "is-done");
  el.classList.add(
    state === "pending" ? "is-pending" : state === "active" ? "is-active" : "is-done"
  );
  const icon = el.querySelector(".progress-step-icon");
  if (icon) {
    icon.textContent =
      state === "done" ? "✅" : state === "active" ? "⏳" : "○";
  }
}

async function renderHome() {
  const sizesRes = await fetch("/sizes");
  const sizes = await sizesRes.json();
  const themesRes = await fetch("/themes");
  const themes = await themesRes.json();
  /** @type {{ id: string, label: string, family?: string, description?: string, pricing?: string, recommended_steps?: number | null }[]} */
  let imageModels = [];
  try {
    const imageModelsRes = await fetch("/image-models");
    if (imageModelsRes.ok) imageModels = await imageModelsRes.json();
  } catch {
    /* keep auto-only if endpoint unavailable */
  }
  /** @type {{ languages: { id: string, label: string, default_voice?: string }[], voices: { id: string, label: string }[] }} */
  let voiceApi = { languages: [], voices: [] };
  try {
    const vr = await fetch("/voices");
    if (vr.ok) voiceApi = await vr.json();
  } catch {
    /* offline or wrong origin */
  }

  app.innerHTML = `
    <div id="loading-overlay" class="loading-overlay" hidden data-progress-card-id="progress-card" data-progress-card-return-id="progress-card-holder">
      <canvas class="loading-canvas" width="300" height="200" aria-hidden="true"></canvas>
      <div class="loading-progress-slot" aria-live="polite"></div>
    </div>
    <div class="container container-main">
      <h1 class="page-title">SudarVid</h1>
      <p class="muted page-lead">Turn a topic into an animated slide video.</p>

      <div class="row">
        <div class="col-form">
          <div class="card topic-hero-card">
            <label class="field-label topic-hero-label" for="topic">What do you want to teach?</label>
            <textarea id="topic" class="hero-textarea" placeholder="e.g. How photosynthesis works"
              rows="5" autocomplete="off"></textarea>
            <div class="topic-meta" aria-live="polite">
              <span id="topicCount" class="topic-count">0 words · 0 characters</span>
            </div>
          </div>

          <div class="card form-options-card">
            <p class="wizard-hint"><span class="wizard-hint-num">Steps 1–5</span> Optional details — expand any section</p>
            <div class="accordion" id="mainAccordion">
              <div class="accordion-item" data-key="audience">
                <button type="button" class="accordion-trigger" aria-expanded="false">
                  <span class="accordion-trigger-inner">
                    <span class="accordion-icon" aria-hidden="true">👥</span>
                    <span class="accordion-step-num">1</span>
                    <span>Audience</span>
                  </span>
                  <span class="accordion-chevron" aria-hidden="true">›</span>
                </button>
                <div class="accordion-panel">
                  <div class="chip-row" id="chips-audience">
                    <button type="button" class="chip" data-value="beginner">Beginner</button>
                    <button type="button" class="chip selected" data-value="intermediate">Intermediate</button>
                    <button type="button" class="chip" data-value="expert">Expert</button>
                  </div>
                </div>
              </div>
              <div class="accordion-item" data-key="length">
                <button type="button" class="accordion-trigger" aria-expanded="false">
                  <span class="accordion-trigger-inner">
                    <span class="accordion-icon" aria-hidden="true">⏱</span>
                    <span class="accordion-step-num">2</span>
                    <span>Length</span>
                  </span>
                  <span class="accordion-chevron" aria-hidden="true">›</span>
                </button>
                <div class="accordion-panel">
                  <div class="chip-row" id="chips-length">
                    <button type="button" class="chip" data-value="short">Short ~2 min</button>
                    <button type="button" class="chip selected" data-value="medium">Medium ~5 min</button>
                    <button type="button" class="chip" data-value="long">Long ~10 min</button>
                  </div>
                </div>
              </div>
              <div class="accordion-item" data-key="style">
                <button type="button" class="accordion-trigger" aria-expanded="false">
                  <span class="accordion-trigger-inner">
                    <span class="accordion-icon" aria-hidden="true">🎨</span>
                    <span class="accordion-step-num">3</span>
                    <span>Style</span>
                  </span>
                  <span class="accordion-chevron" aria-hidden="true">›</span>
                </button>
                <div class="accordion-panel">
                  <div id="themes" class="themes-mood-root"></div>
                </div>
              </div>
              <div class="accordion-item" data-key="voice">
                <button type="button" class="accordion-trigger" aria-expanded="false">
                  <span class="accordion-trigger-inner">
                    <span class="accordion-icon" aria-hidden="true">🔊</span>
                    <span class="accordion-step-num">4</span>
                    <span>Voice</span>
                  </span>
                  <span class="accordion-chevron" aria-hidden="true">›</span>
                </button>
                <div class="accordion-panel">
                  <label class="field-label"><input type="checkbox" id="includeTts" checked /> Include narration (TTS)</label>
                  <label class="field-label" for="voiceOverride">Narration voice</label>
                  <div class="voice-row">
                    <select id="voiceOverride" class="field-input voice-select"></select>
                    <button type="button" class="btn-voice-sample" id="btnVoiceSample">Play sample</button>
                  </div>
                </div>
              </div>
              <div class="accordion-item" data-key="advanced">
                <button type="button" class="accordion-trigger" aria-expanded="false">
                  <span class="accordion-trigger-inner">
                    <span class="accordion-icon" aria-hidden="true">⚙️</span>
                    <span class="accordion-step-num">5</span>
                    <span>Advanced</span>
                  </span>
                  <span class="accordion-chevron" aria-hidden="true">›</span>
                </button>
                <div class="accordion-panel">
                  <label class="field-label" for="animationLevel">Animation intensity</label>
                  <div class="animation-slider-row">
                    <span class="animation-slider-label">Subtle</span>
                    <input type="range" id="animationSlider" class="animation-slider" min="0" max="2" step="1" value="1" aria-valuemin="0" aria-valuemax="2" aria-label="Animation intensity from subtle to dynamic" />
                    <span class="animation-slider-label">Dynamic</span>
                  </div>
                  <select id="animationLevel" class="field-input visually-hidden" aria-hidden="true" tabindex="-1">
                    <option value="subtle">Subtle</option>
                    <option value="medium" selected>Medium</option>
                    <option value="dynamic">Dynamic</option>
                  </select>
                  <p class="animation-hint" id="animationHint">Balanced motion between slides</p>
                  <label class="field-label" for="language">Language preset</label>
                  <select id="language" class="field-input"></select>
                  <label class="field-label" for="imageModel">Image model</label>
                  <select id="imageModel" class="field-input"></select>
                  <p id="imageModelHelp" class="field-help">
                    Auto uses server default (<code>TOGETHER_IMAGE_MODEL</code>).
                  </p>
                  <span class="field-label">Video format</span>
                  <div class="video-format-grid" id="videoFormatGrid" role="radiogroup" aria-label="Video format"></div>
                  <select id="videoSize" class="field-input visually-hidden" aria-hidden="true" tabindex="-1"></select>
                </div>
              </div>
            </div>
          </div>

          <div class="generate-bar">
            <button type="button" class="btn-generate" id="btnGenerate">Generate video</button>
          </div>
        </div>

        <div id="progress-card-holder" hidden>
          <div id="progress-card" class="card progress-card">
            <h3>Progress</h3>
            <p class="muted progress-sub">Follow each stage of your video.</p>

            <div id="errorCard" class="error-card" hidden>
              <div class="error-card-row">
                <span class="error-card-icon" aria-hidden="true">❌</span>
                <p class="error-card-msg" id="errorCardMsg"></p>
              </div>
              <div class="error-actions">
                <button type="button" class="btn-retry" id="btnRetry">Retry</button>
                <button type="button" class="btn-secondary" id="btnOpenDeck" hidden>Open generated deck</button>
                <button type="button" class="btn-secondary" id="btnFloatingPreview" hidden>Floating preview</button>
              </div>
            </div>
            <div id="warnCard" class="warn-card" hidden>
              <p class="warn-card-msg" id="warnCardMsg"></p>
            </div>

            <div class="progress-visual" id="progressVisual">
              <div class="progress-bar-track" aria-hidden="true">
                <div class="progress-bar-fill" id="jobProgressBar"></div>
              </div>
              <ul class="progress-steps" id="progressSteps">
                <li class="progress-step is-pending" data-step="plan">
                  <span class="progress-step-icon" aria-hidden="true">○</span>
                  <span class="progress-step-text">Plotting your scenes…</span>
                </li>
                <li class="progress-step is-pending" data-step="images">
                  <span class="progress-step-icon" aria-hidden="true">○</span>
                  <span class="progress-step-text">Generating images…</span>
                </li>
                <li class="progress-step is-pending" data-step="audio">
                  <span class="progress-step-icon" aria-hidden="true">○</span>
                  <span class="progress-step-text">Creating narration…</span>
                </li>
                <li class="progress-step is-pending" data-step="render">
                  <span class="progress-step-icon" aria-hidden="true">○</span>
                  <span class="progress-step-text">Rendering video…</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div id="floatingPreviewPanel" class="floating-preview-panel" hidden>
      <div class="floating-preview-head">
        <span>Generated Deck Preview</span>
        <button type="button" id="btnFloatingClose" class="floating-close">Close</button>
      </div>
      <iframe id="floatingPreviewFrame" title="Generated deck preview"></iframe>
    </div>
  `;

  const overlay = document.getElementById("loading-overlay");
  const errorCard = document.getElementById("errorCard");
  const errorCardMsg = document.getElementById("errorCardMsg");
  const progressCardHolder = document.getElementById("progress-card-holder");
  const btnOpenDeck = document.getElementById("btnOpenDeck");
  const btnFloatingPreview = document.getElementById("btnFloatingPreview");
  const floatingPreviewPanel = document.getElementById("floatingPreviewPanel");
  const floatingPreviewFrame = document.getElementById("floatingPreviewFrame");
  const btnFloatingClose = document.getElementById("btnFloatingClose");
  const warnCard = document.getElementById("warnCard");
  const warnCardMsg = document.getElementById("warnCardMsg");
  const jobProgressBar = document.getElementById("jobProgressBar");
  const stepPlan = document.querySelector('[data-step="plan"]');
  const stepImages = document.querySelector('[data-step="images"]');
  const stepAudio = document.querySelector('[data-step="audio"]');
  const stepRender = document.querySelector('[data-step="render"]');
  const imagesLabel = stepImages.querySelector(".progress-step-text");

  const voiceSelect = document.getElementById("voiceOverride");
  const langSelect = document.getElementById("language");
  const imageModelSelect = document.getElementById("imageModel");
  const imageModelHelp = document.getElementById("imageModelHelp");
  langSelect.innerHTML = "";
  const langList =
    voiceApi.languages && voiceApi.languages.length
      ? voiceApi.languages
      : [{ id: "en", label: "English (default US)" }];
  for (const L of langList) {
    const opt = document.createElement("option");
    opt.value = L.id;
    opt.textContent = L.label;
    langSelect.appendChild(opt);
  }
  if (!Array.from(langSelect.options).some((o) => o.value === "en")) {
    const opt = document.createElement("option");
    opt.value = "en";
    opt.textContent = "English";
    langSelect.appendChild(opt);
  }
  langSelect.value = "en";

  voiceSelect.innerHTML = "";
  const defVoiceOpt = document.createElement("option");
  defVoiceOpt.value = "";
  defVoiceOpt.textContent = "Default (follow language)";
  voiceSelect.appendChild(defVoiceOpt);
  for (const v of voiceApi.voices || []) {
    const opt = document.createElement("option");
    opt.value = v.id;
    opt.textContent = v.label;
    voiceSelect.appendChild(opt);
  }

  const imageModelById = new Map();
  imageModelSelect.innerHTML = "";
  const autoOpt = document.createElement("option");
  autoOpt.value = "";
  autoOpt.textContent = "Auto (recommended)";
  imageModelSelect.appendChild(autoOpt);
  for (const m of imageModels) {
    if (!m || !m.id) continue;
    imageModelById.set(m.id, m);
    const opt = document.createElement("option");
    opt.value = m.id;
    const family = m.family ? ` (${m.family})` : "";
    opt.textContent = `${m.label || m.id}${family}`;
    imageModelSelect.appendChild(opt);
  }
  imageModelSelect.value = "";

  function updateImageModelHelp() {
    const selectedId = imageModelSelect.value.trim();
    if (!selectedId) {
      imageModelHelp.innerHTML = "Auto uses server default (<code>TOGETHER_IMAGE_MODEL</code>).";
      return;
    }
    const meta = imageModelById.get(selectedId);
    if (!meta) {
      imageModelHelp.textContent = selectedId;
      return;
    }
    const pricing = meta.pricing ? `Pricing: ${meta.pricing}.` : "";
    const stepNote =
      typeof meta.recommended_steps === "number"
        ? ` Recommended steps: ${meta.recommended_steps}.`
        : "";
    imageModelHelp.textContent = `${meta.description || meta.label || selectedId} ${pricing}${stepNote}`.trim();
  }
  imageModelSelect.addEventListener("change", updateImageModelHelp);
  updateImageModelHelp();

  document.getElementById("btnVoiceSample").addEventListener("click", async () => {
    let vid = voiceSelect.value.trim();
    if (!vid) {
      const preset = (voiceApi.languages || []).find((x) => x.id === langSelect.value);
      vid = preset && preset.default_voice ? preset.default_voice : "";
    }
    if (!vid) return;
    const a = new Audio(`/tts/preview?voice=${encodeURIComponent(vid)}`);
    try {
      await a.play();
    } catch {
      /* autoplay or network */
    }
  });

  const sizeSelect = document.getElementById("videoSize");
  const formatGrid = document.getElementById("videoFormatGrid");
  /** @type {{ icon: string, short: string, match?: (s: typeof sizes[0]) => boolean }[]} */
  const formatDefs = [
    { icon: "🖥", short: "Landscape", match: (s) => s.width === 1920 && s.height === 1080 },
    { icon: "📱", short: "Portrait", match: (s) => s.width === 1080 && s.height === 1920 },
    { icon: "⬛", short: "Square", match: (s) => s.width === 1080 && s.height === 1080 },
    { icon: "🎬", short: "Ultrawide", match: (s) => s.width === 2560 && s.height === 1080 },
    { icon: "⚙️", short: "Custom", match: (s) => s.width == null }
  ];

  for (const s of sizes) {
    const opt = document.createElement("option");
    if (s.width == null) {
      opt.value = JSON.stringify({ width: 1920, height: 1080 });
      opt.textContent = s.label || "Custom (defaults 16:9)";
    } else {
      opt.value = JSON.stringify({ width: s.width, height: s.height });
      opt.textContent = `${s.label} (${s.width}×${s.height})`;
    }
    if (s.width === 1920 && s.height === 1080) opt.selected = true;
    sizeSelect.appendChild(opt);
  }

  function syncFormatSelection() {
    const val = sizeSelect.value;
    for (const btn of formatGrid.querySelectorAll(".video-format-btn")) {
      btn.classList.toggle("selected", btn.dataset.sizeValue === val);
    }
  }

  for (const def of formatDefs) {
    const s = sizes.find(def.match);
    if (!s) continue;
    const opt = Array.from(sizeSelect.options).find((o) => {
      if (s.width == null) return o.textContent.includes("Custom");
      try {
        const j = JSON.parse(o.value);
        return j.width === s.width && j.height === s.height;
      } catch {
        return false;
      }
    });
    if (!opt) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "video-format-btn";
    btn.dataset.sizeValue = opt.value;
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-checked", opt.selected ? "true" : "false");
    btn.innerHTML = `<span class="video-format-icon" aria-hidden="true">${def.icon}</span><span class="video-format-text">${def.short}</span>`;
    btn.addEventListener("click", () => {
      sizeSelect.value = opt.value;
      syncFormatSelection();
      for (const b of formatGrid.querySelectorAll(".video-format-btn")) {
        b.setAttribute("aria-checked", b === btn ? "true" : "false");
      }
    });
    formatGrid.appendChild(btn);
  }
  syncFormatSelection();

  const animSlider = document.getElementById("animationSlider");
  const animSelect = document.getElementById("animationLevel");
  const animHint = document.getElementById("animationHint");
  const animLevels = [
    { v: "subtle", hint: "Minimal motion — calm and focused" },
    { v: "medium", hint: "Balanced motion between slides" },
    { v: "dynamic", hint: "Stronger transitions and emphasis" }
  ];
  function syncAnimFromSlider() {
    const i = Number(animSlider.value);
    animSelect.value = animLevels[i].v;
    animHint.textContent = animLevels[i].hint;
  }
  animSlider.addEventListener("input", syncAnimFromSlider);
  syncAnimFromSlider();

  const topicEl = document.getElementById("topic");
  const topicCountEl = document.getElementById("topicCount");
  function updateTopicCount() {
    const t = topicEl.value;
    const words = t.trim() ? t.trim().split(/\s+/).length : 0;
    topicCountEl.textContent = `${words} word${words === 1 ? "" : "s"} · ${t.length} character${t.length === 1 ? "" : "s"}`;
  }
  topicEl.addEventListener("input", updateTopicCount);
  updateTopicCount();
  topicEl.focus();

  const state = {
    theme: "neo_retro_dev",
    audience: "intermediate",
    length: "medium",
    generating: false
  };

  function setJobProgress(pct) {
    if (jobProgressBar) jobProgressBar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
  }

  function resetProgressSteps() {
    setJobProgress(0);
    setStepEl(stepPlan, "pending");
    setStepEl(stepImages, "pending");
    setStepEl(stepAudio, "pending");
    setStepEl(stepRender, "pending");
    imagesLabel.textContent = "Generating images…";
  }

  function showError(msg, friendly) {
    const text = friendly || "Something went wrong. Try again or adjust your topic.";
    const detail = (msg && String(msg).trim()) || "";
    errorCardMsg.style.whiteSpace = "pre-wrap";
    if (detail) {
      const cap = 1200;
      const clipped = detail.length > cap ? `${detail.slice(0, cap)}…` : detail;
      errorCardMsg.textContent = `${text}\n\n${clipped}`;
    } else {
      errorCardMsg.textContent = text;
    }
    errorCard.hidden = false;
    // Don't create empty layout space while the overlay is active.
    if (progressCardHolder && overlay.hidden) progressCardHolder.hidden = false;
  }

  function hideError() {
    errorCard.hidden = true;
    errorCardMsg.textContent = "";
    if (btnOpenDeck) btnOpenDeck.hidden = true;
    if (btnFloatingPreview) btnFloatingPreview.hidden = true;
    if (progressCardHolder && warnCard) progressCardHolder.hidden = warnCard.hidden;
  }
  function showWarning(msg) {
    if (!warnCard || !warnCardMsg) return;
    warnCardMsg.textContent = String(msg || "").trim();
    warnCard.hidden = !warnCardMsg.textContent;
    // Don't create empty layout space while the overlay is active.
    if (!warnCard.hidden && progressCardHolder && overlay.hidden) progressCardHolder.hidden = false;
  }
  function hideWarning() {
    if (!warnCard || !warnCardMsg) return;
    warnCard.hidden = true;
    warnCardMsg.textContent = "";
    if (progressCardHolder && errorCard) progressCardHolder.hidden = errorCard.hidden;
  }
  function currentDeckUrl() {
    if (!lastAttemptedJobId) return "";
    return `/render/${encodeURIComponent(lastAttemptedJobId)}/slides.html`;
  }
  function setRecoveryActionsVisible(show) {
    if (btnOpenDeck) btnOpenDeck.hidden = !show;
    if (btnFloatingPreview) btnFloatingPreview.hidden = !show;
  }
  function openDeckNewTab() {
    const url = currentDeckUrl();
    if (!url) return;
    window.open(url, "_blank", "noopener,noreferrer");
  }
  function toggleFloatingPreview() {
    if (!floatingPreviewPanel || !floatingPreviewFrame) return;
    const opening = floatingPreviewPanel.hidden;
    if (opening) {
      const url = currentDeckUrl();
      if (!url) return;
      floatingPreviewFrame.src = url;
      floatingPreviewPanel.hidden = false;
      if (btnFloatingPreview) btnFloatingPreview.textContent = "Hide floating preview";
    } else {
      floatingPreviewPanel.hidden = true;
      floatingPreviewFrame.src = "";
      if (btnFloatingPreview) btnFloatingPreview.textContent = "Floating preview";
    }
  }
  function closeFloatingPreview() {
    if (!floatingPreviewPanel || !floatingPreviewFrame) return;
    floatingPreviewPanel.hidden = true;
    floatingPreviewFrame.src = "";
    if (btnFloatingPreview) btnFloatingPreview.textContent = "Floating preview";
  }

  let progressPct = 0;
  let imageTotal = 0;
  /** @type {{ metaphor?: string, subtitle?: string, steps?: Record<string,string> } | null} */
  let loaderCopy = null;

  function loaderStepText(key, fallback) {
    const s = loaderCopy && loaderCopy.steps ? loaderCopy.steps[key] : "";
    return (s && String(s).trim()) || fallback;
  }

  function bumpProgress(delta, label) {
    progressPct = Math.min(95, progressPct + delta);
    setLoading(overlay, state.generating, label, progressPct);
    setJobProgress(progressPct);
  }

  const themesRoot = document.getElementById("themes");
  const byMood = groupThemesByMood(themes);
  themesRoot.innerHTML = MOOD_ORDER.map((m) => {
    const list = byMood[m.id] || [];
    if (!list.length) return "";
    return `
      <div class="themes-mood-section">
        <h4 class="themes-mood-label">${escapeHtml(m.label)}</h4>
        <div class="themes-grid">${list.map((t) => buildThemeCard(t, state.theme)).join("")}</div>
      </div>
    `;
  }).join("");

  for (const card of themesRoot.querySelectorAll(".theme-preview-card")) {
    card.addEventListener("click", () => {
      state.theme = card.dataset.themeId;
      for (const el of themesRoot.querySelectorAll(".theme-preview-card")) {
        const on = el.dataset.themeId === state.theme;
        el.classList.toggle("selected", on);
        el.setAttribute("aria-pressed", on ? "true" : "false");
      }
      document.dispatchEvent(
        new CustomEvent("themeChange", { detail: { themeId: state.theme } })
      );
    });
  }

  function selectChip(container, value) {
    for (const el of container.querySelectorAll(".chip")) {
      el.classList.toggle("selected", el.dataset.value === value);
    }
  }

  document.getElementById("chips-audience").addEventListener("click", (e) => {
    const t = e.target.closest(".chip");
    if (!t) return;
    state.audience = t.dataset.value;
    selectChip(document.getElementById("chips-audience"), state.audience);
  });
  document.getElementById("chips-length").addEventListener("click", (e) => {
    const t = e.target.closest(".chip");
    if (!t) return;
    state.length = t.dataset.value;
    selectChip(document.getElementById("chips-length"), state.length);
  });

  for (const acc of document.querySelectorAll(".accordion-item")) {
    const trig = acc.querySelector(".accordion-trigger");
    trig.addEventListener("click", () => {
      const open = acc.classList.toggle("open");
      trig.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  async function runGeneration() {
    if (state.generating) return;
    const topic = document.getElementById("topic").value.trim();
    if (topic.length < 3) {
      showError("", "Please enter a short lesson description (at least 3 characters).");
      return;
    }

    hideError();
    hideWarning();
    setRecoveryActionsVisible(false);
    if (floatingPreviewPanel) floatingPreviewPanel.hidden = true;
    if (floatingPreviewFrame) floatingPreviewFrame.src = "";
    state.generating = true;
    progressPct = 8;
    imageTotal = 0;
    resetProgressSteps();
    setStepEl(stepPlan, "active");
    setLoading(overlay, true, "Starting your video…", progressPct);
    setJobProgress(progressPct);
    document.getElementById("btnGenerate").disabled = true;

    const len = lengthPreset(state.length);
    const video_size = JSON.parse(document.getElementById("videoSize").value);
    const includeTts = document.getElementById("includeTts").checked;
    const voiceOverride = document.getElementById("voiceOverride").value.trim();
    const imageModel = imageModelSelect.value.trim();

    lastJobPrefs = {
      topic,
      audience: state.audience,
      length: state.length,
      theme: state.theme
    };

    const body = {
      topic,
      audience: audienceLabel(state.audience),
      language: document.getElementById("language").value.trim() || "en",
      theme: state.theme,
      slide_count: len.slide_count,
      video_size,
      animation_level: document.getElementById("animationLevel").value,
      include_tts: includeTts,
      include_music: false,
      output_html: true,
      output_mp4: true,
      target_duration_seconds: len.target_duration_seconds
    };
    if (voiceOverride) body.voice_override = voiceOverride;
    if (imageModel) body.image_model = imageModel;

    try {
      const res = await fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      let data = {};
      try {
        data = await res.json();
      } catch {
        /* non-JSON */
      }
      if (!res.ok) {
        const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || "");
        if (res.status === 404) {
          showError(
            detail,
            "No SudarVid API on this origin. Open the app at http://127.0.0.1:8000 (run uvicorn sudarvid.server:app), not Live Server or a static HTML file."
          );
        } else {
          showError(detail, "We could not start the job. Check your topic and try again.");
        }
        setLoading(overlay, false, "", 0);
        state.generating = false;
        document.getElementById("btnGenerate").disabled = false;
        resetProgressSteps();
        return;
      }

      progressPct = 12;
      lastAttemptedJobId = data.job_id;
      setJobProgress(progressPct);
      setLoading(overlay, true, "Queued — plotting your scenes…", progressPct);

      const stream = new EventSource(`/stream/${encodeURIComponent(data.job_id)}`);
      let streamDone = false;

      stream.addEventListener("loader_copy", (evt) => {
        let payload = {};
        try {
          payload = JSON.parse(evt.data || "{}");
        } catch {
          payload = {};
        }
        if (!payload || typeof payload !== "object") return;
        loaderCopy = payload;

        const sub = (payload.subtitle && String(payload.subtitle).trim()) || "";
        if (sub) setLoading(overlay, true, sub, progressPct);

        const planLabel = stepPlan && stepPlan.querySelector(".progress-step-text");
        const audioLabel = stepAudio && stepAudio.querySelector(".progress-step-text");
        const renderLabel = stepRender && stepRender.querySelector(".progress-step-text");
        if (planLabel) planLabel.textContent = loaderStepText("plan", "Plotting your scenes…");
        if (audioLabel) audioLabel.textContent = loaderStepText("audio", "Creating narration…");
        if (renderLabel) renderLabel.textContent = loaderStepText("render", "Rendering video…");
      });

      stream.addEventListener("error", () => {
        if (streamDone) return;
        streamDone = true;
        try {
          stream.close();
        } catch {
          /* ignore */
        }
        showError(
          "",
          "Lost connection to the server. If this page was opened from Live Server (port 5500) or a file URL, use http://127.0.0.1:8000 instead so /generate and /stream resolve."
        );
        setLoading(overlay, false, "", 0);
        state.generating = false;
        document.getElementById("btnGenerate").disabled = false;
        resetProgressSteps();
      });

      stream.addEventListener("planning", () => {
        setStepEl(stepPlan, "active");
        bumpProgress(18, loaderStepText("plan", "Plotting your scenes…"));
      });

      stream.addEventListener("images_start", (evt) => {
        setStepEl(stepPlan, "done");
        setStepEl(stepImages, "active");
        try {
          const p = JSON.parse(evt.data);
          imageTotal = p.total || imageTotal;
          if (imageTotal) {
            imagesLabel.textContent = `${loaderStepText("images", "Generating images…").replace(/…$/, "")} 0/${imageTotal}…`;
          } else {
            imagesLabel.textContent = loaderStepText("images", "Generating images…");
          }
        } catch {
          imagesLabel.textContent = loaderStepText("images", "Generating images…");
        }
      });

      stream.addEventListener("image_progress", (evt) => {
        let payload = {};
        try {
          payload = JSON.parse(evt.data);
        } catch {
          return;
        }
        const cur = payload.current;
        const tot = payload.total || imageTotal;
        if (tot) imageTotal = tot;
        if (cur != null && imageTotal) {
          imagesLabel.textContent = `${loaderStepText("images", "Generating images…").replace(/…$/, "")} ${cur}/${imageTotal}…`;
        }
        setStepEl(stepPlan, "done");
        setStepEl(stepImages, "active");
        bumpProgress(
          4,
          `${loaderStepText("images", "Generating images…").replace(/…$/, "")} (${cur || "…"}/${imageTotal || "…"})…`
        );
      });

      stream.addEventListener("audio", () => {
        setStepEl(stepImages, "done");
        setStepEl(stepAudio, "active");
        bumpProgress(14, loaderStepText("audio", "Creating narration…"));
      });

      stream.addEventListener("rendering", () => {
        setStepEl(stepAudio, "done");
        setStepEl(stepRender, "active");
        bumpProgress(10, loaderStepText("render", "Building slide deck…"));
      });

      stream.addEventListener("rendering_video", () => {
        setStepEl(stepRender, "active");
        bumpProgress(8, loaderStepText("rendering_video", "Encoding video file…"));
      });
      stream.addEventListener("video_failed", (evt) => {
        let payload = {};
        try {
          payload = JSON.parse(evt.data || "{}");
        } catch {
          payload = {};
        }
        const msg = payload.message || "MP4 export skipped. Install Playwright browsers with: playwright install";
        showWarning(msg);
      });

      stream.addEventListener("status", (evt) => {
        let payload = {};
        try {
          payload = JSON.parse(evt.data);
        } catch {
          return;
        }
        if (payload.status === "running" && payload.step === "planning") {
          setStepEl(stepPlan, "active");
          bumpProgress(5, "Plotting your scenes…");
        }
        if (payload.status === "done" && !streamDone) {
          streamDone = true;
          if (payload.warning || payload.error) {
            const notice = String(payload.warning || payload.error || "").trim();
            if (notice) {
              try {
                sessionStorage.setItem("sudarvid_completion_notice", notice);
              } catch {
                /* ignore quota / private mode */
              }
            }
          }
          setStepEl(stepPlan, "done");
          setStepEl(stepImages, "done");
          setStepEl(stepAudio, "done");
          setStepEl(stepRender, "done");
          imagesLabel.textContent = "Generating images…";
          progressPct = 100;
          setJobProgress(100);
          setLoading(overlay, true, "Done — opening preview…", 100);
          stream.close();
          setTimeout(() => {
            hideWarning();
            hideError();
            setLoading(overlay, false, "", 0);
            state.generating = false;
            document.getElementById("btnGenerate").disabled = false;
            window.location.assign(`/preview/${encodeURIComponent(data.job_id)}`);
          }, 600);
        }
        if (payload.status === "error" && !streamDone) {
          streamDone = true;
          const errDetail = payload.error || "";
          showError(errDetail, "Something went wrong while building your video. Try again or adjust your topic.");
          setRecoveryActionsVisible(Boolean(lastAttemptedJobId));
          setLoading(overlay, false, "", 0);
          state.generating = false;
          document.getElementById("btnGenerate").disabled = false;
          stream.close();
          resetProgressSteps();
        }
      });
    } catch (err) {
      const s = String(err && err.message ? err.message : err);
      const likelyOrigin =
        s.includes("Failed to fetch") || s.includes("NetworkError") || s.includes("fetch");
      showError(
        s,
        likelyOrigin
          ? "Cannot reach the API. Run uvicorn and open http://127.0.0.1:8000 (same host as this app)."
          : "A network error occurred. Check your connection and try again."
      );
      setLoading(overlay, false, "", 0);
      state.generating = false;
      document.getElementById("btnGenerate").disabled = false;
      resetProgressSteps();
    }
  }

  document.getElementById("btnGenerate").onclick = runGeneration;
  if (btnOpenDeck) btnOpenDeck.onclick = openDeckNewTab;
  if (btnFloatingPreview) btnFloatingPreview.onclick = toggleFloatingPreview;
  if (btnFloatingClose) btnFloatingClose.onclick = closeFloatingPreview;
  document.getElementById("btnRetry").onclick = () => {
    hideError();
    if (lastJobPrefs) {
      topicEl.value = lastJobPrefs.topic;
      state.audience = lastJobPrefs.audience;
      state.length = lastJobPrefs.length;
      state.theme = lastJobPrefs.theme;
      selectChip(document.getElementById("chips-audience"), state.audience);
      selectChip(document.getElementById("chips-length"), state.length);
      for (const el of themesRoot.querySelectorAll(".theme-preview-card")) {
        const on = el.dataset.themeId === state.theme;
        el.classList.toggle("selected", on);
        el.setAttribute("aria-pressed", on ? "true" : "false");
      }
      updateTopicCount();
    }
    topicEl.focus();
    runGeneration();
  };
}

if (isPreviewRoute()) {
  renderPreview(getPreviewJobId());
} else {
  renderHome();
}
