# AI-OPS-107 Prompt Pack

Objective:
- Ship citizen product KPI heartbeat retention v1 so `/citizen` KPI trend monitoring can compact history safely while keeping strict parity guarantees in last-N windows.

Acceptance gates:
- Add product KPI heartbeat compaction reporter (`scripts/report_citizen_product_kpis_heartbeat_compaction.py`).
- Add product KPI heartbeat compaction-window parity reporter (`scripts/report_citizen_product_kpis_heartbeat_compaction_window.py`).
- Preserve incident classes: `failed`, `degraded`, `strict`, `malformed`, `contract_incomplete`, and threshold violations for `unknown_rate`, `time_to_first_answer`, and `drilldown_click_rate`.
- Add deterministic tests for compaction preservation + compaction-window strict parity.
- Wire `just` report/check lanes and include new tests in `citizen-test-product-kpis-heartbeat`.
- Publish strict evidence bundle under `docs/etl/sprints/AI-OPS-107/evidence/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`compaction_strict_fail_reasons=[]`, `compaction_window_status=ok`, `incident_missing_in_compacted=0`).
