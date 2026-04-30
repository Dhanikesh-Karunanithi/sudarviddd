# Course Generation Learnings

This document captures what materially improved course quality across recent handcrafted examples and how those learnings should guide SudarVid generation.

## Benchmark Set

- `sudavidadv/examples/https-protocol-video-lesson.html`
- `sudavidadv/examples/design-thinking-masterclass.html`
- `sudavidadv/examples/behavioral-economics-video-course.html`

## What Improved Most

- **Course-first narrative:** Better outputs moved from "slide deck with visuals" to "lesson journey" with clear chapter arc and learning objective per chapter.
- **Concept-specific visuals:** Each chapter visualized the concept itself (scale for loss aversion, sticky walls for ideation) instead of generic card stacks.
- **Typography motion hierarchy:** Staggered entry (`kicker -> title -> body`) made scenes readable and cinematic.
- **Premium color systems:** Multi-theme palettes with chapter-level accent shifts and smooth token interpolation outperformed generic neon palettes.
- **Meaningful interaction:** Quiz/checkpoint interactions tied to learning outcomes (not novelty points or XP-only gamification).
- **Timeline clarity:** A persistent timestamp pill in the scrubber improved orientation and "video-like" feel.

## Repeatable Design Patterns

- **8-scene default arc:** intro, objectives, core concepts, applied example, practice, reflection, checkpoint, wrap-up.
- **Progress model:** Scene-local progress variable (`p` from 0..1) drives all chapter-specific animations.
- **Theme model:** Base palette + per-chapter accent pairs (`accent`, `accent2`, glow token).
- **Interaction model:** At least one formative interaction every 2-3 chapters and one summative challenge near the end.
- **Motion constraints:** Prefer subtle-to-medium motion; avoid decorative animation that does not aid comprehension.

## Quality Rubric (Generator Output Acceptance)

A generated lesson is acceptable only when all of these are true:

- **Pedagogy:** Learner can articulate at least 3 concrete takeaways from the scenes.
- **Narrative:** Chapters have logical progression and references to prior steps.
- **Visual semantics:** At least 70% of chapter visuals are concept-specific (not generic templates).
- **Interactivity:** Includes both formative and summative checks with feedback.
- **Aesthetic quality:** Palette coherence, typography hierarchy, and timeline UX meet premium standards.

## Anti-Patterns To Avoid

- Generic "AI style" cyan/purple defaults for all topics.
- Gamification elements that do not reinforce learning (for example, arbitrary XP counters).
- Repeated card-only layouts with no scene metaphor.
- Long dense paragraphs with no progressive reveal.
- Interactions that are present but not tied to concept mastery.
