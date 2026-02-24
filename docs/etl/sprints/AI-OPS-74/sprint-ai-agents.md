# AI-OPS-74 Prompt Pack

Objective:
- Ship a deterministic first-answer accelerator for `/citizen` that recommends concern+item with explicit audit links and fallback behavior.

Acceptance gates:
- Add shared accelerator module (`ui/citizen/first_answer_accelerator.js`).
- Wire onboarding/UI CTA to jump directly to recommended first answer.
- Include explicit evidence links in recommendation surfaces.
- Add strict tests for ranking/fallback + UI contract markers.
- Wire local server and GH pages build to ship the new module.

Status update (2026-02-23):
- Implemented and validated with reproducible sprint evidence.
