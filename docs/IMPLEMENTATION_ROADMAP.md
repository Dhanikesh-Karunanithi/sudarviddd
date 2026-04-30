# Implementation Roadmap

This roadmap turns premium course learnings into phased SudarVid upgrades with low integration risk.

## Phase 1: Documentation and Contracts (Now)

- Finalize learnings and premium output spec.
- Define standalone vs integrated architecture boundaries.
- Align README and integration notes.

Exit criteria:

- Docs exist and are accepted by Sudar/SudarVid stakeholders.

## Phase 2: Premium Schema Introduction

- Add a premium planning schema in `content_planner.py` for chapter-first outputs.
- Keep current slide schema working in parallel.
- Add config switch (`engine_mode`) in request/config types.

Exit criteria:

- Same API still works for classic mode.
- Premium schema can be produced by planner (even before full premium renderer).

## Phase 3: Premium Renderer Runtime

- Add premium template and runtime pathway (separate from `base.html.j2`).
- Implement scene progress animation model (`p` per chapter).
- Add scrubber timestamp pill and chapter sync.

Exit criteria:

- Premium HTML lesson renders end-to-end from generated payload.

## Phase 4: Interaction and Pedagogy Layer

- Add interaction blocks to planner output (formative + summative).
- Add runtime interaction state and feedback handling.
- Ensure interaction copy explains reasoning.

Exit criteria:

- At least 2 meaningful interactions in premium lessons.

## Phase 5: Main Sudar Integration

- Add integration adapter for main Sudar (HTTP or library call).
- Keep standalone server fully functional.
- Add integration smoke tests for output artifacts.

Exit criteria:

- Main Sudar can request premium lessons with stable contract.

## Phase 6: Quality Gate and Rollout

- Add benchmark evaluation based on:
  - `behavioral-economics-video-course.html`
  - `design-thinking-masterclass.html`
  - `https-protocol-video-lesson.html`
- Create a release checklist (pedagogy, visual quality, interaction quality, runtime stability).
- Roll out premium mode behind a feature flag.

Exit criteria:

- Premium mode meets rubric and does not regress classic mode.

