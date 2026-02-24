# AI-OPS-73 Prompt Pack

Objective:
- Harden the citizen onboarding funnel with a deterministic "best next action" path and strict UX contract tests.

Acceptance gates:
- Add reusable onboarding funnel contract module (`ui/citizen/onboarding_funnel.js`).
- Wire "Siguiente" CTA in UI (`data-onboard-next`) to jump to the best next onboarding action.
- Add strict tests for funnel logic and UI contract markers.
- Expose onboarding module in local server and GH Pages build copy.

Status update (2026-02-23):
- Implemented and validated with contract tests and sprint evidence artifacts.
