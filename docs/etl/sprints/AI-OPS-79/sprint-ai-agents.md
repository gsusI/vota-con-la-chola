# AI-OPS-79 Prompt Pack

Objective:
- Ship an evidence trust panel in `/citizen` that makes stance trust explicit: method, source-age freshness, trust level, and direct drill-down links.

Acceptance gates:
- Add a deterministic trust-panel module (`evidence_trust_panel_v1`) with stable freshness tiers and trust levels.
- Render trust markers in `/citizen` cards (`data-evidence-trust-panel`, `data-evidence-trust-freshness`) without backend dependency.
- Serve the new citizen asset from local explorer server and keep GH Pages copy parity.
- Add strict tests for module contract + UI contract + server route wiring.
- Keep citizen regressions green (preset/mobile/first-answer/unknown/concern-pack quality).
- Publish sprint evidence and closeout under `docs/etl/sprints/AI-OPS-79/`.

Status update (2026-02-23):
- Implemented and validated with reproducible sprint evidence.
