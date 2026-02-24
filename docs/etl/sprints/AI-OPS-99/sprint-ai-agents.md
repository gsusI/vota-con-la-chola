# AI-OPS-99 Prompt Pack

Objective:
- Ship coherence drilldown observability v1 so `/citizen -> /explorer-temas` deep-link replay health is tracked with strict machine contracts.

Acceptance gates:
- Add coherence drilldown outcomes digest reporter (`scripts/report_citizen_coherence_drilldown_outcomes.py`).
- Add append-only heartbeat reporter for coherence outcomes (`scripts/report_citizen_coherence_drilldown_outcomes_heartbeat.py`).
- Add strict last-N window reporter for coherence outcomes heartbeat (`scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_window.py`).
- Track threshold-violation counts/rates for replay success, contract-complete click rate, and replay failure rate.
- Add deterministic fixture/tests for digest, heartbeat, and window strict behavior.
- Wire new `just` report/check/test lanes and include coherence outcomes heartbeat tests in `citizen-release-regression-suite`.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`outcomes_status=ok`, `heartbeat_status=ok`, `window_status=ok`, all violation counters at `0`).
