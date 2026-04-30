# Premium Video Course Spec

This is the target output contract for SudarVid premium course generation.

## 1) Output Contract

Premium mode should generate:

- `slides.html` with scene-based course runtime
- `slides_manifest.json` with chapter/scene metadata
- optional `audio/voiceover.mp3`
- optional `video/output.mp4`

## 2) Course Structure Contract

Default structure is 8 chapters (configurable):

1. Context/Hook
2. Objective framing
3. Core concept 1
4. Core concept 2
5. Applied example
6. Practice/decision exercise
7. Transfer principle
8. Summative challenge + recap

Each chapter must define:

- `learning_goal`
- `visual_metaphor`
- `scene_copy` (`kicker`, `title`, `body`)
- optional `interaction`
- `transition_intent`

## 3) Runtime UX Contract

- Scene transitions with readability-first timing.
- Typography entrance hierarchy (`kicker`, `title`, `body`) with staggered delays.
- Timeline with chapter markers and scrubber timestamp pill.
- Keyboard controls: `Space`, `ArrowLeft`, `ArrowRight`.
- Theme switcher support (at least 3 premium themes).

## 4) Interaction Contract

Minimum per lesson:

- 1 formative interaction before chapter 6.
- 1 summative challenge at or near final chapter.
- Feedback must include "why", not only "correct/incorrect".

Supported interaction types:

- single-select quiz
- scenario decision
- slider tradeoff
- ranking choice

## 5) Visual System Contract

- Theme tokens: `bg`, `panel`, `ink`, `muted`, `line`, `accent`, `accent2`, `glow`.
- Chapter-level accent progression with smooth interpolation.
- Concept-specific visuals for at least 70% of chapters.
- Avoid over-reliance on repeated card grids.

## 6) Content Quality Rules

- No chapter is allowed to be purely decorative.
- Copy must be concise, explicit, and instructional.
- Every chapter body should connect to prior context or next action.
- Practice questions should test application, not only recall.

## 7) Evaluation Checklist

Run this checklist per generated lesson:

- [ ] Clear objective appears in first 2 chapters.
- [ ] At least 2 scenes include concept-specific visual metaphors.
- [ ] At least 2 interactions produce explanatory feedback.
- [ ] Timeline and chapter chips are synchronized.
- [ ] Palette consistency holds across all chapters.
- [ ] Generated lesson is understandable without narration audio.

