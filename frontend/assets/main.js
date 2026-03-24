const app = document.getElementById("app");

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
          <p><a href="/download/${encodeURIComponent(jobId)}/slides.html">slides.html</a></p>
          <p><a href="/download/${encodeURIComponent(jobId)}/audio/voiceover.mp3">voiceover.mp3</a></p>
          <p><a href="/download/${encodeURIComponent(jobId)}/video/output.mp4">output.mp4</a></p>
          <p class="muted">If a file is missing, it was not generated for this job.</p>
        </div>
      </div>
    </div>
  `;
}

async function renderHome() {
  app.innerHTML = `
    <div class="container">
      <h1 style="margin:0 0 14px;">SudarVid</h1>
      <div class="row">
        <div class="card">
          <h3 style="margin-top:0;">Generate</h3>
          <label>Topic</label>
          <textarea id="topic">AI turns messy ideas into polished slide decks</textarea>
          <label>Audience</label>
          <input id="audience" value="general audience" />
          <label>Language</label>
          <input id="language" value="en" />
          <label>Theme</label>
          <div id="themes" class="themes-grid"></div>
          <label>Slide count</label>
          <input id="slideCount" value="5" />
          <label>Animation level</label>
          <select id="animationLevel">
            <option value="subtle">subtle</option>
            <option value="medium" selected>medium</option>
            <option value="dynamic">dynamic</option>
          </select>
          <button id="btnGenerate">Generate</button>
        </div>
        <div class="card">
          <h3 style="margin-top:0;">Progress</h3>
          <p class="muted">SSE stream from <code>/stream/{job_id}</code>.</p>
          <ul id="statusList" class="status-list"></ul>
        </div>
      </div>
    </div>
  `;

  const statusList = document.getElementById("statusList");
  const state = { theme: "neo_retro_dev" };

  function appendStatus(line) {
    const li = document.createElement("li");
    li.textContent = line;
    statusList.appendChild(li);
  }

  const themesRes = await fetch("/themes");
  const themes = await themesRes.json();
  const themesRoot = document.getElementById("themes");
  themesRoot.innerHTML = "";
  for (const t of themes) {
    const card = document.createElement("button");
    card.className = "theme-card";
    card.type = "button";
    card.innerHTML = `
      <div class="theme-name">${t.label}</div>
      <div class="swatches">
        <span class="swatch" style="background:${swatchColor(t, "bg")}"></span>
        <span class="swatch" style="background:${swatchColor(t, "accent")}"></span>
        <span class="swatch" style="background:${swatchColor(t, "secondary")}"></span>
      </div>
    `;
    card.onclick = () => {
      state.theme = t.id;
      for (const el of themesRoot.querySelectorAll(".theme-card")) {
        el.classList.remove("selected");
      }
      card.classList.add("selected");
    };
    if (t.id === state.theme) {
      card.classList.add("selected");
    }
    themesRoot.appendChild(card);
  }

  document.getElementById("btnGenerate").onclick = async () => {
    statusList.innerHTML = "";
    const body = {
      topic: document.getElementById("topic").value,
      audience: document.getElementById("audience").value,
      language: document.getElementById("language").value,
      theme: state.theme,
      slide_count: Number.parseInt(document.getElementById("slideCount").value, 10),
      animation_level: document.getElementById("animationLevel").value,
      include_tts: true,
      include_music: false,
      output_html: true,
      output_mp4: false
    };
    const res = await fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    appendStatus(`job: ${data.job_id}`);

    const stream = new EventSource(`/stream/${encodeURIComponent(data.job_id)}`);
    stream.onmessage = (evt) => {
      appendStatus(evt.data);
    };
    stream.addEventListener("status", (evt) => {
      const payload = JSON.parse(evt.data);
      appendStatus(`status: ${payload.status}`);
      if (payload.status === "done") {
        stream.close();
        window.location.assign(`/v/${encodeURIComponent(data.job_id)}`);
      }
      if (payload.status === "error") {
        stream.close();
      }
    });
    stream.addEventListener("image_progress", (evt) => {
      const payload = JSON.parse(evt.data);
      appendStatus(payload.message || `image_${payload.current}_of_${payload.total}`);
    });
    stream.addEventListener("planning", () => appendStatus("planning"));
    stream.addEventListener("audio", () => appendStatus("audio"));
    stream.addEventListener("rendering", () => appendStatus("rendering"));
  };
}

if (isPreviewRoute()) {
  renderPreview(getPreviewJobId());
} else {
  renderHome();
}
