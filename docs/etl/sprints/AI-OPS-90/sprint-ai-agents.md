# AI-OPS-90 Prompt Pack

Objective:
- Ship mobile latency trend digest v1 for `/citizen`: append-only heartbeat + strict last-N window SLO focused on `p90` stability.

Acceptance gates:
- Add heartbeat reporter `scripts/report_citizen_mobile_observability_heartbeat.py` to append deduped JSONL entries from the latest mobile observability digest.
- Add window reporter `scripts/report_citizen_mobile_observability_heartbeat_window.py` with strict thresholds for `failed/degraded` and explicit `p90` threshold-violation counts/rates.
- Add dedicated tests for both reporters and expose `just` wrappers for `test/report/check` flows.
- Integrate new heartbeat test lane into `citizen-release-regression-suite`.
- Publish sprint evidence under `docs/etl/sprints/AI-OPS-90/evidence/` with stable latest JSON artifacts.
- Keep GH Pages build green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`heartbeat_status=ok`, `window_status=ok`, `p90_margin_ms=27.0`).
