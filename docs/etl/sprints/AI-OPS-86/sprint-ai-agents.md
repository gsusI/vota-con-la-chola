# AI-OPS-86 Prompt Pack

Objective:
- Ship trust-to-action nudges v1 in `/citizen`: deterministic “next best evidence click” hints with strict telemetry KPI checks.

Acceptance gates:
- Add deterministic trust-action nudge selection logic (low trust/unknown-first, explainable tie-breaks).
- Surface explicit next-evidence nudges in concern/topic/dashboard compare views.
- Capture local telemetry for nudge shown/click events with debug export APIs.
- Add strict machine-readable KPI reporter (`ok|degraded|failed`) for nudge adoption/clickthrough.
- Add tests + `just` wrappers and include lane in `citizen-release-regression-suite`.
- Keep GH Pages build + release hardening green and publish sprint evidence/docs.

Status update (2026-02-23):
- Implemented and validated with strict evidence.
