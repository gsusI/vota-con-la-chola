# AI-OPS-98 Prompt Pack

Objective:
- Ship citizen product KPI heartbeat v1 so `/citizen` has an append-only trend lane for KPI contract outcomes with strict last-N threshold checks.

Acceptance gates:
- Add append-only heartbeat reporter for product KPI digest (`scripts/report_citizen_product_kpis_heartbeat.py`).
- Add strict window reporter for product KPI heartbeat (`scripts/report_citizen_product_kpis_heartbeat_window.py`).
- Track threshold-violation counts/rates in last-N for `unknown_rate`, `time_to_first_answer_seconds`, and `drilldown_click_rate`.
- Add deterministic tests for heartbeat and window strict behavior.
- Wire `just` report/check/test lanes and include KPI heartbeat tests in `citizen-release-regression-suite`.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`product_kpi_status=ok`, `heartbeat_status=ok`, `window_status=ok`, threshold-violation counters all zero).
