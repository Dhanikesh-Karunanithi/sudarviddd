
# Complete Cursor Prompt Plan for SudarVid UI & Video Overhaul

Below is a structured brief you can paste into Cursor's composer. It is broken into phases — share them one at a time or all at once.

***

## Phase 1 — Apple-Style UI Design System

**Paste this into Cursor:**

> **Goal:** Redesign the entire SudarVid UI to feel like it was designed by Apple — SF Pro typography, frosted glass, generous whitespace, subtle depth, and motion that feels intentional.
>
> **Design Tokens to establish (create a `static/css/design-tokens.css` file):**
> ```css
> :root {
>   --apple-bg: #000000;
>   --apple-surface: rgba(28, 28, 30, 0.85);
>   --apple-glass: rgba(255, 255, 255, 0.06);
>   --apple-border: rgba(255, 255, 255, 0.10);
>   --apple-text-primary: #F5F5F7;
>   --apple-text-secondary: rgba(245,245,247,0.60);
>   --apple-accent: #2997FF;
>   --apple-radius-sm: 10px;
>   --apple-radius-md: 18px;
>   --apple-radius-lg: 28px;
>   --apple-blur: blur(24px) saturate(180%);
>   --apple-font: -apple-system, "SF Pro Display", "SF Pro Text", BlinkMacSystemFont, system-ui, sans-serif;
>   --apple-mono: "SF Mono", ui-monospace, monospace;
>   --apple-shadow: 0 20px 60px rgba(0,0,0,0.55), 0 4px 16px rgba(0,0,0,0.35);
> }
> ```
>
> **Apply these tokens to:**
> 1. The `body` and `#deck` background → pure `#000` with ambient gradient
> 2. The `#sudarvid-player-ui` → frosted glass (`backdrop-filter: var(--apple-blur); background: var(--apple-surface);`) with a hairline `1px solid var(--apple-border)` top border
> 3. All `<button>` elements → pill shape (`border-radius: 980px`), `background: var(--apple-glass)`, hover lifts with subtle scale and glow
> 4. The scrubber (`#sudarvid-scrub`) → custom track with `-webkit-appearance: none`, thin 3px track, circular thumb matching `--apple-accent`
> 5. Replace all hard-coded `{{ theme.* }}` font references inside the `<style>` tag with a CSS variable fallback to `var(--apple-font)` when no theme font is set

***

## Phase 2 — Theme Selector Preview Cards

**Paste this into Cursor:**

> **Goal:** Replace the current color-swatches-only theme selector (shown in attached screenshot) with full visual preview cards — a 16-theme grid where each card shows a mini slide thumbnail rendered in that theme's actual colors, fonts, and style.
>
> **Create a new Django/Jinja template: `templates/theme_selector.html.j2`**
>
> Requirements:
> - Each card: `240×135px` (16:9), rounded corners (`border-radius: 18px`), with:
>   - A mini slide rendered using that theme's `bg_color`, `text_color`, `accent_color`
>   - Theme name in `font-heading` style
>   - 3 color dot swatches at the bottom
>   - Selected state: `2px solid var(--apple-accent)` border + gentle scale `1.04` + glow box-shadow
>   - Hover state: `scale(1.02)` + shadow lift
> - Grid: `repeat(auto-fill, minmax(240px, 1fr))` with `gap: 16px`
> - Clicking a card fires a `CustomEvent('themeChange', { detail: { themeId } })` on `document`
> - Add a `data-theme-id` attribute to each card for identification
> - Render all 16 themes defined in `sudarvid/themes.py` (or wherever themes are stored) as cards
>
> **The mini slide inside each card should contain:**
> - A fake slide title ("Sample Slide") in `font-heading`
> - A thin accent bar (matching `accent_color`)
> - 2 fake bullet lines (grey bars)
> - A subtle dark overlay background image placeholder
>
> Use only inline SVG and CSS for the mini-slide — no external images needed.

***

## Phase 3 — Dynamic Slide Scene Engine

**Paste this into Cursor:**

> **Goal:** Transform each slide from a static HTML panel into a living, breathing scene with motion graphics, morph transitions, and cinematic energy. The output video should feel like an Apple keynote — not a PowerPoint export.
>
> **Upgrade `templates/base.html.j2` as follows:**
>
> **1. Add a SVG Particle/Ambient Layer to every slide:**
> ```html
> <div class="slide-ambient" aria-hidden="true">
>   <svg class="ambient-svg" viewBox="0 0 1280 720" preserveAspectRatio="xMidYMid slice">
>     <!-- Animated gradient orb -->
>     <defs>
>       <radialGradient id="orb-{{slide.index}}" cx="70%" cy="30%" r="55%">
>         <stop offset="0%" stop-color="{{ theme.accent_color }}" stop-opacity="0.18"/>
>         <stop offset="100%" stop-color="transparent" stop-opacity="0"/>
>       </radialGradient>
>     </defs>
>     <ellipse cx="900" cy="200" rx="500" ry="380" fill="url(#orb-{{slide.index}})">
>       <animateTransform attributeName="transform" type="translate"
>         values="0 0; -30 20; 0 0" dur="9s" repeatCount="indefinite"/>
>     </ellipse>
>   </svg>
> </div>
> ```
>
> **2. Add FLIP/Morph Slide Transitions using the Web Animations API:**
> In `static/js/sudarvid.js`, when transitioning slides:
> - Use `element.animate([{transform:'scale(1.04) translateY(12px)', opacity:0}, {transform:'scale(1)', opacity:1}], {duration:600, easing:'cubic-bezier(0.22,0.68,0,1.2)', fill:'both'})` for incoming slides
> - Use `element.animate([{transform:'scale(1)', opacity:1}, {transform:'scale(0.97) translateY(-8px)', opacity:0}], {duration:380, easing:'ease-in', fill:'both'})` for outgoing slides
> - Queue the incoming animation to start after 220ms to create an overlap "morph" feel
> - For title elements specifically, use `clip-path` animation: `clip-path: inset(0 100% 0 0)` → `clip-path: inset(0 0% 0 0)` to create a text-reveal wipe effect
>
> **3. Stagger child element entrances (already partially done — enhance it):**
> - The `slide-title` should wipe in from left using clip-path (300ms)
> - `slide-accent-bar` should expand from 0 to full width (400ms, 100ms delay)
> - `slide-subtitle` fades up (500ms, 200ms delay)
> - Bullet/step cards pop in with spring: `cubic-bezier(0.34, 1.56, 0.64, 1)` (each 80ms apart)
> - `slide-big-stat` should count up from 0 using a JS counter animation
>
> **4. Add a Cinematic Progress Bar** at the very top of `#deck`:
> ```html
> <div id="slide-progress-bar" style="
>   position:absolute; top:0; left:0; height:3px;
>   background: linear-gradient(90deg, var(--apple-accent), #bf5af2);
>   width:0%; transition:width 0.4s ease; z-index:100;
> "></div>
> ```
> Update its width in JS as slides advance.
>
> **5. Image Ken Burns + Parallax:**
> All `.slide-image` elements should have:
> ```css
> .slide.active .slide-image {
>   animation: kenBurns 12s ease-in-out both;
>   transform-origin: center center;
> }
> @keyframes kenBurns {
>   0%   { transform: scale(1.08) translate(0px, 0px); }
>   50%  { transform: scale(1.14) translate(-18px, -10px); }
>   100% { transform: scale(1.10) translate(8px, 6px); }
> }
> ```

***

## Phase 4 — Smarter Content Input (UX)

**Paste this into Cursor:**

> **Goal:** Improve the video generation form UX so it doesn't feel like a wall of questions. The user should be able to get great output with minimal input, but also optionally go deep.
>
> **Redesign the input form with these changes:**
>
> 1. **Single focused input first:** Start with just one large textarea: *"What do you want to teach?"* — pill-shaped, Apple-style, with a placeholder like *"e.g. How photosynthesis works"*
>
> 2. **Progressive disclosure accordion below it** — collapsed by default, expandable sections:
>    - 🎯 **Audience** (beginner / intermediate / expert toggle chips)
>    - ⏱ **Length** (Short 2min / Medium 5min / Long 10min toggle chips)
>    - 🎨 **Style** (theme selector cards from Phase 2)
>    - 🔊 **Voice** (voice selection if TTS is enabled)
>    - ⚙️ **Advanced** (animation level, language, aspect ratio)
>
> 3. **Smart defaults:** If user skips the accordion, use sensible auto-detected defaults (medium length, Neo-Retro Dev theme, dynamic animation)
>
> 4. **Generate button:** Large, full-width, glowing CTA button:
>    ```css
>    background: linear-gradient(135deg, #2997FF 0%, #bf5af2 100%);
>    border-radius: 14px;
>    font-size: 18px;
>    font-weight: 600;
>    letter-spacing: -0.02em;
>    box-shadow: 0 0 40px rgba(41,151,255,0.35);
>    ```
>
> 5. **Loading state:** When generating, show a full-screen overlay with:
>    - Animated SVG waveform or pulsing logo
>    - Live status text ("Generating script…", "Creating visuals…", "Rendering video…")
>    - A progress bar that fills as each stage completes

***

## Phase 5 — Video Output Quality

**Paste this into Cursor:**

> **Goal:** The rendered video output (`Playwright` screen capture) should look like a cinematic production, not a browser recording.
>
> 1. **Add an intro scene** (first 2 seconds): Full black screen, the topic title sweeps in with a scale+fade, then dissolves into slide 1. Implement as a special `layout_kind == 'intro'` slide type.
>
> 2. **Add an outro scene** (last 2 seconds): Fade to black with the "SudarVid" wordmark centered, white, fading out.
>
> 3. **Inter-slide transition overlay:** For the 400ms between slides, briefly flash a thin horizontal light sweep (`linear-gradient` animated left-to-right at full viewport width) to add cinematic flash.
>
> 4. **Text rendering:** Add `text-rendering: optimizeLegibility; -webkit-font-smoothing: antialiased; font-feature-settings: "kern" 1, "liga" 1;` to all text elements for crisper video output.
>
> 5. **Aspect ratio support:** Ensure the `#deck` respects both 16:9 (1280×720 landscape) and 9:16 (720×1280 vertical/Shorts) and centers correctly in the Playwright capture viewport.

