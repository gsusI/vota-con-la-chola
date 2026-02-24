# AI-OPS-75 Prompt Pack

Objective:
- Ship unknown/no_signal explainability v2 in `/citizen` with explicit causes and deterministic "what would reduce uncertainty" hints across summary and comparison cards.

Acceptance gates:
- Add shared explainability module (`ui/citizen/unknown_explainability.js`) reusable by UI and Node tests.
- Wire explainability hints in dashboard summary, concern summary, and topic-detail party cards.
- Add strict module + UI contract tests and keep first-answer regression green.
- Wire local server + GH pages build to publish the new module.
- Publish sprint evidence and closeout with PASS/FAIL adjudication.

Status update (2026-02-23):
- Implemented and validated with reproducible sprint evidence.
