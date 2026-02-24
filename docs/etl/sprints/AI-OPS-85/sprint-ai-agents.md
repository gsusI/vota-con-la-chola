# AI-OPS-85 Prompt Pack

Objective:
- Ship concern-pack outcome telemetry v1 for `/citizen`: pack selection usage + weak-pack follow-through, with strict machine-readable checks and release regression integration.

Acceptance gates:
- Add local telemetry instrumentation in `ui/citizen/index.html` for `pack_selected`, `pack_cleared`, and `topic_open_with_pack`.
- Expose debug/export helpers to extract summarized and raw concern-pack outcome telemetry.
- Add strict reporter `scripts/report_citizen_concern_pack_outcomes.py` with `ok|degraded|failed` status contract.
- Add fixtures/tests + `just` wrappers for test/report/check lanes.
- Include new lane in `citizen-release-regression-suite` and keep release hardening green.
- Publish sprint artifacts under `docs/etl/sprints/AI-OPS-85/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence.
