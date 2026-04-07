(function () {
  const slides = Array.from(document.querySelectorAll(".slide"));

  const animLevel =
    (typeof window !== "undefined" && window.SUDARVID_ANIMATION_LEVEL) ||
    (document.body && document.body.dataset && document.body.dataset.animationLevel) ||
    "medium";

  const progressBar = document.getElementById("slide-progress-bar");

  function setDeckProgress(seconds, totalSeconds) {
    if (!progressBar || totalSeconds <= 0) return;
    const pct = Math.min(100, Math.max(0, (seconds / totalSeconds) * 100));
    progressBar.style.width = pct + "%";
  }

  let lastShownIndex = -1;
  let transitionLock = false;

  function triggerCaptureSweep(newIndex) {
    if (!window.IS_CAPTURE) return;
    if (lastShownIndex < 0 || newIndex === lastShownIndex) return;
    const sweep = document.getElementById("sudarvid-capture-sweep");
    if (!sweep) return;
    sweep.classList.remove("sweep-active");
    void sweep.offsetWidth;
    sweep.classList.add("sweep-active");
    window.setTimeout(function () {
      sweep.classList.remove("sweep-active");
    }, 450);
  }

  function animateStatNumber(el) {
    const raw = (el.textContent || "").trim();
    const match = raw.match(/^([\d,.]+)(.*)$/);
    if (!match) return;
    const target = parseFloat(match[1].replace(/,/g, ""));
    if (Number.isNaN(target)) return;
    const suffix = match[2] || "";
    const start = performance.now();
    const dur = 900;
    function frame(t) {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      const v = Math.round(target * eased);
      el.textContent = v + suffix;
      if (p < 1) {
        window.requestAnimationFrame(frame);
      }
    }
    window.requestAnimationFrame(frame);
  }

  var captionEl = null;
  var captionWordEls = [];
  var captionTokenCount = 0;
  var activeCaptionIdx = -1;
  var activeCaptionProgress = -1;
  var activeCaptionTimesMs = null;

  function tokenizeCaption(text) {
    return String(text || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
  }

  function renderCaptionForSlide(idx) {
    if (!captionEl) {
      captionEl = document.getElementById("sudarvid-caption");
    }
    if (!captionEl) return;
    var meta = (window.SUDARVID_SLIDES || [])[idx];
    activeCaptionTimesMs = meta && Array.isArray(meta.caption_times_ms) ? meta.caption_times_ms : null;
    var tokens =
      meta && Array.isArray(meta.caption_words) && meta.caption_words.length
        ? meta.caption_words
        : tokenizeCaption(meta && meta.narration ? meta.narration : "");
    captionEl.innerHTML = "";
    captionWordEls = [];
    captionTokenCount = tokens.length;
    if (!tokens.length) {
      return;
    }
    var frag = document.createDocumentFragment();
    for (var i = 0; i < tokens.length; i++) {
      var span = document.createElement("span");
      span.className = "sv-word";
      span.textContent = tokens[i];
      frag.appendChild(span);
      captionWordEls.push(span);
      if (i < tokens.length - 1) {
        frag.appendChild(document.createTextNode(" "));
      }
    }
    captionEl.appendChild(frag);
  }

  function updateCaptionProgress(slideIdx, slideProgress, secondsIntoSlide) {
    if (slideIdx !== activeCaptionIdx) {
      activeCaptionIdx = slideIdx;
      activeCaptionProgress = -1;
      renderCaptionForSlide(slideIdx);
    }
    if (!captionWordEls.length) return;
    var p = Math.max(0, Math.min(0.999, slideProgress || 0));
    // If we have word-level timestamps, drive highlighting from the audio clock
    // instead of evenly pacing tokens across the slide duration.
    var upto = -1;
    if (activeCaptionTimesMs && activeCaptionTimesMs.length) {
      var tMs = Math.max(0, (secondsIntoSlide || 0) * 1000);
      // Avoid frequent DOM churn: only update if we've progressed at least one word boundary.
      // We still keep activeCaptionProgress updated for the fallback gate.
      upto = 0;
      for (var k = 0; k < activeCaptionTimesMs.length; k++) {
        if (tMs >= activeCaptionTimesMs[k]) {
          upto = k;
        } else {
          break;
        }
      }
    } else {
      if (Math.abs(p - activeCaptionProgress) < 0.01) return;
      upto = Math.floor(p * captionTokenCount);
    }
    activeCaptionProgress = p;
    upto = Math.max(0, Math.min(captionTokenCount - 1, upto));
    for (var i = 0; i < captionWordEls.length; i++) {
      var el = captionWordEls[i];
      el.classList.toggle("is-spoken", i < upto);
      el.classList.toggle("is-current", i === upto);
    }
  }

  function runSlideActivated(index) {
    const slide = slides[index];
    if (!slide) return;
    triggerCaptureSweep(index);
    const statEl = slide.querySelector(".slide-big-stat");
    if (statEl) {
      animateStatNumber(statEl);
    }
    const titleEl = slide.querySelector(".slide-title");
    if (titleEl && animLevel === "dynamic") {
      try {
        titleEl.animate(
          [{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)" }],
          { duration: 300, easing: "ease-out", fill: "both" }
        );
      } catch (e) {}
    }
  }

  function showSlide(index) {
    const i = Math.max(0, Math.min(slides.length - 1, index));
    updateCaptionProgress(i, 0);

    if (animLevel !== "dynamic" || transitionLock) {
      const prev = slides.findIndex(function (s) {
        return s.classList.contains("active");
      });
      slides.forEach(function (s, j) {
        s.classList.toggle("active", j === i);
      });
      if (prev !== i) {
        runSlideActivated(i);
      }
      lastShownIndex = i;
      return i;
    }

    const prevIdx = slides.findIndex(function (s) {
      return s.classList.contains("active");
    });
    if (prevIdx === i) {
      return i;
    }

    transitionLock = true;
    const outgoing = slides[prevIdx];
    const incoming = slides[i];

    const a1 = outgoing.animate(
      [
        { transform: "scale(1)", opacity: 1 },
        { transform: "scale(0.97) translateY(-8px)", opacity: 0 }
      ],
      { duration: 380, easing: "ease-in", fill: "both" }
    );

    a1.finished.then(function () {
      outgoing.classList.remove("active");
      incoming.classList.add("active");
      const a2 = incoming.animate(
        [
          { transform: "scale(1.04) translateY(12px)", opacity: 0 },
          { transform: "scale(1)", opacity: 1 }
        ],
        { duration: 600, easing: "cubic-bezier(0.22,0.68,0,1.2)", fill: "both" }
      );
      a2.finished.then(function () {
        transitionLock = false;
        runSlideActivated(i);
        lastShownIndex = i;
      });
    });

    return i;
  }

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

  function buildTimings() {
    const slideDurations = slides.map(function (s) {
      return parseFloat(s.dataset.duration || "5");
    });
    const slideStartTimes = [];
    let t = 0;
    slideDurations.forEach(function (d) {
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
          playPromise.catch(function () {});
        }
      } catch (e) {}

      audio.addEventListener(
        "playing",
        function () {
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
      setDeckProgress(now, totalDurationSeconds);

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
      const start = slideStartTimes[idx] || 0;
      const dur = Math.max(0.001, (slideStartTimes[idx + 1] || totalDurationSeconds) - start);
      updateCaptionProgress(idx, (now - start) / dur, now - start);

      if (now < totalDurationSeconds) {
        window.requestAnimationFrame(update);
      }
    }

    showSlide(0);
    runSlideActivated(0);
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
      audio.addEventListener("error", function () {
        if (hint) {
          hint.textContent = "Audio failed to load. Check that audio/voiceover.mp3 is reachable.";
        }
      });
      audio.addEventListener("playing", function () {
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
      setDeckProgress(now, totalDurationSeconds);
      const idx = computeSlideIndex(now);
      showSlide(idx);
      const start = slideStartTimes[idx] || 0;
      const dur = Math.max(0.001, (slideStartTimes[idx + 1] || totalDurationSeconds) - start);
      updateCaptionProgress(idx, (now - start) / dur, now - start);

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
        p.catch(function () {
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
          overlay.addEventListener("click", function () {
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
        const onPlaying = function () {
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

    btnPrev.addEventListener("click", function () {
      goPrev();
    });
    btnNext.addEventListener("click", function () {
      goNext();
    });
    btnPlay.addEventListener("click", function () {
      togglePlayPause();
    });

    scrub.addEventListener("pointerdown", function () {
      scrubbing = true;
    });
    scrub.addEventListener("pointerup", function () {
      scrubbing = false;
      playStartPerf = performance.now();
      if (!paused) {
        scheduleTick();
      }
    });
    scrub.addEventListener("input", function () {
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

    document.addEventListener("keydown", function (e) {
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
      play: function () {
        play();
      },
      pause: function () {
        pause();
      },
      seekTo,
      goPrev,
      goNext
    };

    setScrubVisual(0);
    showSlide(0);
    runSlideActivated(0);
    syncPlayButton();

    paused = false;
    timeAtPause = 0;
    playStartPerf = performance.now();
    useAudioClock = false;
    if (audio) {
      const onPlaying = function () {
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
    const chrome = document.getElementById("sudarvid-chrome");
    if (chrome) {
      chrome.remove();
    }
    startCapturePlayback();
  } else {
    startInteractivePlayer();
  }
})();
