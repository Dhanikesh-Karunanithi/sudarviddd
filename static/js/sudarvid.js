(function () {
  const slides = Array.from(document.querySelectorAll(".slide"));

  if (slides.length === 0) {
    const deck = document.getElementById("deck");
    if (deck) {
      deck.innerHTML =
        '<section class="slide active" data-index="0" data-duration="8" style="display:flex;align-items:center;justify-content:center;padding:3rem;text-align:center;">' +
        '<div class="slide-content" style="max-width:42rem;margin:0 auto;">' +
        '<h1 class="slide-title" style="font-size:clamp(22px,4vw,40px);line-height:1.15;">No slides in this deck</h1>' +
        "<p style=\"margin-top:1.25rem;font-size:clamp(14px,2vw,20px);opacity:0.88;\">" +
        "The generator finished without any slides (empty JSON from the text model). " +
        "Regenerate with a JSON-reliable model or check the server log for warnings." +
        "</p></div></section>";
    }
    const hint = document.getElementById("sudarvid-hint");
    if (hint) {
      hint.textContent = "Nothing to play — regenerate this job.";
    }
    const playBtn = document.getElementById("sudarvid-btn-play");
    if (playBtn) {
      playBtn.disabled = true;
      playBtn.textContent = "N/A";
    }
    return;
  }

  function showSlide(index) {
    const i = Math.max(0, Math.min(slides.length - 1, index));
    slides.forEach((s, j) => s.classList.toggle("active", j === i));
    return i;
  }

  function buildTimings() {
    const slideDurations = slides.map((s) => parseFloat(s.dataset.duration || "5"));
    const slideStartTimes = [];
    let t = 0;
    slideDurations.forEach((d) => {
      slideStartTimes.push(t);
      t += d;
    });
    const totalDurationSeconds = Math.max(t, 0.1);
    return { slideDurations, slideStartTimes, totalDurationSeconds };
  }

  /** Playwright / headless capture: no UI, drive slides from clock only */
  function startCapturePlayback() {
    const audio = document.getElementById("SudarVidVoiceover");
    const { slideStartTimes, totalDurationSeconds } = buildTimings();

    let currentIndex = 0;
    const startPerfMs = performance.now();
    let audioClockEnabled = false;

    if (audio) {
      try {
        audio.currentTime = 0;
        const playPromise = audio.play();
        if (playPromise && typeof playPromise.then === "function") {
          playPromise.catch(() => {});
        }
      } catch (e) {}

      audio.addEventListener(
        "playing",
        () => {
          audioClockEnabled = true;
        },
        { once: true }
      );
    }

    function clockSeconds() {
      if (audio && audioClockEnabled) {
        return audio.currentTime || 0;
      }
      return (performance.now() - startPerfMs) / 1000;
    }

    function update() {
      const now = clockSeconds();

      let idx = slides.length - 1;
      for (let i = slideStartTimes.length - 1; i >= 0; i--) {
        if (now >= slideStartTimes[i]) {
          idx = i;
          break;
        }
      }

      if (idx !== currentIndex) {
        currentIndex = idx;
        showSlide(idx);
      }

      if (now < totalDurationSeconds) {
        window.requestAnimationFrame(update);
      }
    }

    showSlide(0);
    window.requestAnimationFrame(update);
  }

  /** Browser: controls + optional voiceover sync */
  function startInteractivePlayer() {
    const audio = document.getElementById("SudarVidVoiceover");
    const { slideStartTimes, totalDurationSeconds } = buildTimings();

    const ui = document.getElementById("sudarvid-player-ui");
    const btnPrev = document.getElementById("sudarvid-btn-prev");
    const btnPlay = document.getElementById("sudarvid-btn-play");
    const btnNext = document.getElementById("sudarvid-btn-next");
    const scrub = document.getElementById("sudarvid-scrub");
    const timeLabel = document.getElementById("sudarvid-time");
    const hint = document.getElementById("sudarvid-hint");

    if (!ui || !btnPrev || !btnPlay || !btnNext || !scrub || !timeLabel) {
      startCapturePlayback();
      return;
    }

    let paused = true;
    let timeAtPause = 0;
    let playStartPerf = 0;
    let useAudioClock = false;
    let rafId = null;
    let scrubbing = false;
    let audioBlocked = false;

    if (audio) {
      audio.preload = "auto";
      audio.muted = false;
      audio.volume = 1;
      audio.addEventListener("error", () => {
        if (hint) {
          hint.textContent = "Audio failed to load. Check that audio/voiceover.mp3 is reachable.";
        }
      });
      audio.addEventListener("playing", () => {
        audioBlocked = false;
        if (hint) {
          hint.textContent = "Space: play/pause · ← →: slides · Home/End: start/end";
        }
      });
    }

    function formatTime(sec) {
      const s = Math.floor(Math.max(0, sec));
      const m = Math.floor(s / 60);
      const r = s % 60;
      return m + ":" + String(r).padStart(2, "0");
    }

    function computeSlideIndex(seconds) {
      let idx = slides.length - 1;
      for (let i = slideStartTimes.length - 1; i >= 0; i--) {
        if (seconds >= slideStartTimes[i]) {
          idx = i;
          break;
        }
      }
      return idx;
    }

    function getNowSeconds() {
      if (paused) {
        return Math.min(timeAtPause, totalDurationSeconds);
      }
      if (audio && useAudioClock && !audio.paused) {
        return Math.min(audio.currentTime || 0, totalDurationSeconds);
      }
      return Math.min(
        timeAtPause + (performance.now() - playStartPerf) / 1000,
        totalDurationSeconds
      );
    }

    function setScrubVisual(seconds) {
      const pct = (seconds / totalDurationSeconds) * 1000;
      scrub.value = String(Math.min(1000, Math.max(0, pct)));
      timeLabel.textContent =
        formatTime(seconds) + " / " + formatTime(totalDurationSeconds);
    }

    function tick() {
      rafId = null;
      const now = getNowSeconds();
      showSlide(computeSlideIndex(now));

      if (!scrubbing) {
        setScrubVisual(now);
      }

      if (paused) {
        return;
      }

      if (now >= totalDurationSeconds - 0.05) {
        timeAtPause = totalDurationSeconds;
        if (audio) {
          try {
            audio.pause();
            audio.currentTime = totalDurationSeconds;
          } catch (e) {}
        }
        paused = true;
        useAudioClock = false;
        btnPlay.textContent = "Play";
        btnPlay.setAttribute("aria-label", "Play");
        setScrubVisual(totalDurationSeconds);
        return;
      }

      rafId = window.requestAnimationFrame(tick);
    }

    function scheduleTick() {
      if (rafId != null) {
        window.cancelAnimationFrame(rafId);
      }
      rafId = window.requestAnimationFrame(tick);
    }

    function syncPlayButton() {
      btnPlay.textContent = paused ? "Play" : "Pause";
      btnPlay.setAttribute("aria-label", paused ? "Play" : "Pause");
    }

    function tryPlayAudioAt(seconds) {
      if (!audio) {
        return;
      }
      try {
        audio.currentTime = seconds;
        audio.muted = false;
        audio.volume = 1;
      } catch (e) {}
      const p = audio.play();
      if (p && typeof p.then === "function") {
        p.catch(() => {
          useAudioClock = false;
          audioBlocked = true;
          paused = true;
          syncPlayButton();
          if (hint) {
            hint.textContent = "Space: play/pause · ← →: slides · Home/End: start/end";
          }
          const overlay = document.createElement("div");
          overlay.style.cssText =
            "position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;cursor:pointer";
          overlay.innerHTML =
            '<div style="background:#fff;padding:2rem 3rem;border-radius:12px;font-size:1.4rem;font-weight:bold;box-shadow:0 8px 32px rgba(0,0,0,0.25);">▶ Click anywhere to play with audio</div>';
          overlay.addEventListener("click", () => {
            overlay.remove();
            play();
          });
          document.body.appendChild(overlay);
        });
      }
    }

    function play() {
      paused = false;
      playStartPerf = performance.now();
      useAudioClock = false;

      if (audio) {
        const onPlaying = () => {
          useAudioClock = true;
        };
        audio.addEventListener("playing", onPlaying, { once: true });
        tryPlayAudioAt(timeAtPause);
      }

      syncPlayButton();
      scheduleTick();
    }

    function pause() {
      const now = getNowSeconds();
      timeAtPause = Math.min(now, totalDurationSeconds);
      paused = true;
      useAudioClock = false;

      if (audio) {
        try {
          audio.pause();
          audio.currentTime = timeAtPause;
        } catch (e) {}
      }

      if (rafId != null) {
        window.cancelAnimationFrame(rafId);
        rafId = null;
      }

      syncPlayButton();
      setScrubVisual(timeAtPause);
      showSlide(computeSlideIndex(timeAtPause));
    }

    function togglePlayPause() {
      if (paused) {
        play();
      } else {
        pause();
      }
    }

    function seekTo(seconds) {
      const t = Math.max(0, Math.min(totalDurationSeconds, seconds));
      timeAtPause = t;
      if (audio) {
        try {
          audio.currentTime = t;
        } catch (e) {}
      }
      playStartPerf = performance.now();
      showSlide(computeSlideIndex(t));
      if (!scrubbing) {
        setScrubVisual(t);
      }
      if (!paused) {
        scheduleTick();
      }
    }

    function currentSlideIndex() {
      return computeSlideIndex(getNowSeconds());
    }

    function goPrev() {
      const i = currentSlideIndex();
      if (i > 0) {
        seekTo(slideStartTimes[i - 1]);
      } else {
        seekTo(0);
      }
    }

    function goNext() {
      const i = currentSlideIndex();
      if (i < slides.length - 1) {
        seekTo(slideStartTimes[i + 1]);
      } else {
        seekTo(totalDurationSeconds);
      }
    }

    btnPrev.addEventListener("click", () => goPrev());
    btnNext.addEventListener("click", () => goNext());
    btnPlay.addEventListener("click", () => togglePlayPause());

    scrub.addEventListener("pointerdown", () => {
      scrubbing = true;
    });
    scrub.addEventListener("pointerup", () => {
      scrubbing = false;
      playStartPerf = performance.now();
      if (!paused) {
        scheduleTick();
      }
    });
    scrub.addEventListener("input", () => {
      const sec = (parseFloat(scrub.value) / 1000) * totalDurationSeconds;
      timeAtPause = sec;
      if (audio) {
        try {
          audio.currentTime = sec;
        } catch (e) {}
      }
      showSlide(computeSlideIndex(sec));
      timeLabel.textContent =
        formatTime(sec) + " / " + formatTime(totalDurationSeconds);
    });

    document.addEventListener("keydown", (e) => {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) {
        return;
      }
      if (e.code === "Space") {
        e.preventDefault();
        togglePlayPause();
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        goNext();
      } else if (e.code === "Home") {
        e.preventDefault();
        seekTo(0);
      } else if (e.code === "End") {
        e.preventDefault();
        seekTo(slideStartTimes[slides.length - 1] ?? 0);
      }
    });

    window.SudarVid = {
      showSlide,
      play: () => play(),
      pause: () => pause(),
      seekTo,
      goPrev,
      goNext,
    };

    setScrubVisual(0);
    showSlide(0);
    syncPlayButton();

    // Match previous behavior: try to start automatically
    paused = false;
    timeAtPause = 0;
    playStartPerf = performance.now();
    useAudioClock = false;
    if (audio) {
      const onPlaying = () => {
        useAudioClock = true;
      };
      audio.addEventListener("playing", onPlaying, { once: true });
      tryPlayAudioAt(0);
    }
    if (!paused) {
      syncPlayButton();
      scheduleTick();
    }
  }

  if (window.IS_CAPTURE) {
    const ui = document.getElementById("sudarvid-player-ui");
    if (ui) {
      ui.remove();
    }
    startCapturePlayback();
  } else {
    startInteractivePlayer();
  }
})();
