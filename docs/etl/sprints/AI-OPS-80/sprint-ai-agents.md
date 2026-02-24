# AI-OPS-80 Prompt Pack

Objective:
- Ship an accessibility/readability hardening slice for `/citizen` with keyboard-first navigation cues, clearer landmarks, and strict static contract checks.

Acceptance gates:
- Add skip-link + main landmark focus target for keyboard users.
- Add explicit live regions/aria labels for status/banners/sections/search inputs/results region.
- Improve readability defaults (line-height and dense-copy constraints) without altering data semantics.
- Add strict UI contract test + `just` test target.
- Keep regressions green for trust panel, mobile, first-answer, unknown explainability, and concern-pack quality.
- Publish sprint evidence and closeout under `docs/etl/sprints/AI-OPS-80/`.

Status update (2026-02-23):
- Implemented and validated with reproducible sprint evidence.
