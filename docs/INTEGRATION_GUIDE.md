# Integration Guide (Main Sudar <-> SudarVid)

This guide explains how to consume SudarVid from the main Sudar project while preserving SudarVid as a standalone tool.

## Integration Options

## 1) Service Integration (Recommended First)

Use SudarVid as an HTTP service:

- `POST /generate`
- `GET /status/{job_id}`
- `GET /render/{job_id}/slides.html`
- optional download/export endpoints

Pros:

- clean process boundary
- easiest to deploy independently
- versioning can be pinned via service image/tag

## 2) Library Integration (Tighter Coupling)

Import SudarVid in-process and call `sudarvid.core.generate_video(...)`.

Pros:

- no HTTP hop

Cons:

- tighter dependency and release coupling

## Stable Request Fields to Use

- `topic`
- `audience`
- `language`
- `theme`
- `slide_count`
- `learning_objectives`
- `difficulty`
- `source_notes`
- `constraints`
- `include_tts`
- `output_html`
- `output_mp4`

Future (planned):

- `engine_mode` (`classic` or `premium`)

## Output Contract for Integrators

Do not parse internals of HTML. Consume only:

- `slides.html`
- `slides_manifest.json`
- `audio/voiceover.mp3` when present
- `video/output.mp4` when present

## Deployment and Versioning

- Pin a specific commit/tag of SudarVid from main Sudar.
- Record compatible SudarVid API/version in main Sudar config.
- Upgrade via staged rollout: dev -> staging -> production.

## Failure Handling

If media generation fails:

- still publish `slides.html` if available
- report non-fatal media errors explicitly
- retry only media-specific stages where possible

