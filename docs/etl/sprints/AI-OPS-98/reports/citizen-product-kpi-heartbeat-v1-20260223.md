# Citizen Product KPI Heartbeat v1 (AI-OPS-98)

Date:
- 2026-02-23

Goal:
- Add an append-only KPI trend lane with strict last-N checks for the citizen KPI contract (`unknown_rate`, `time_to_first_answer_seconds`, `drilldown_click_rate`).

What shipped:
- New heartbeat reporter:
  - `scripts/report_citizen_product_kpis_heartbeat.py`
  - appends deduped JSONL rows from KPI digest and preserves threshold/check context per run.
- New window reporter:
  - `scripts/report_citizen_product_kpis_heartbeat_window.py`
  - evaluates strict `last N` thresholds for:
    - status (`failed`, `degraded`)
    - completeness (`contract_incomplete`)
    - KPI-threshold violations (`unknown_rate`, `tfa`, `drilldown`)
  - enforces latest-row checks (`latest_not_failed_ok`, `latest_contract_complete_ok`, `latest_thresholds_ok`).
- New fixture:
  - `tests/fixtures/citizen_product_kpi_events_sample.jsonl`
  - deterministic telemetry source to produce complete KPI digest in heartbeat lanes.
- New tests:
  - `tests/test_report_citizen_product_kpis_heartbeat.py`
  - `tests/test_report_citizen_product_kpis_heartbeat_window.py`
- `just` wiring:
  - new vars: `citizen_product_kpi_heartbeat_*`
  - new lanes:
    - `just citizen-test-product-kpis-heartbeat`
    - `just citizen-report-product-kpis-heartbeat`
    - `just citizen-check-product-kpis-heartbeat`
    - `just citizen-report-product-kpis-heartbeat-window`
    - `just citizen-check-product-kpis-heartbeat-window`
  - heartbeat test lane added to `just citizen-release-regression-suite`

Validation:
- `python3 -m py_compile scripts/report_citizen_product_kpis_heartbeat.py scripts/report_citizen_product_kpis_heartbeat_window.py tests/test_report_citizen_product_kpis_heartbeat.py tests/test_report_citizen_product_kpis_heartbeat_window.py`
- `just citizen-test-product-kpis-heartbeat`
- `just citizen-check-product-kpis-heartbeat`
- `just citizen-check-product-kpis-heartbeat-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict run result:
- KPI digest check pre-step: PASS (`status=ok`, `unknown_rate=0.175676`, `time_to_first_answer_seconds=30.0`, `drilldown_click_rate=0.5`)
- Heartbeat check: PASS (`status=ok`, `history_size_after=1`, `strict_fail_reasons=[]`)
- Window check: PASS (`status=ok`, `entries_in_window=1`, `contract_incomplete_in_window=0`, KPI-violation counters all `0`, `strict_fail_reasons=[]`)

Evidence:
- `docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_latest.json`
- `docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_heartbeat_latest.json`
- `docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_heartbeat_window_latest.json`
- `docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_20260223T143048Z.json`
- `docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_heartbeat_20260223T143048Z.json`
- `docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_heartbeat_window_20260223T143048Z.json`
- `docs/etl/sprints/AI-OPS-98/evidence/just_citizen_test_product_kpis_heartbeat_20260223T143048Z.txt`
- `docs/etl/sprints/AI-OPS-98/evidence/just_citizen_check_product_kpis_heartbeat_20260223T143048Z.txt`
- `docs/etl/sprints/AI-OPS-98/evidence/just_citizen_check_product_kpis_heartbeat_window_20260223T143048Z.txt`
- `docs/etl/sprints/AI-OPS-98/evidence/just_citizen_release_regression_suite_20260223T143048Z.txt`
- `docs/etl/sprints/AI-OPS-98/evidence/just_explorer_gh_pages_build_20260223T143048Z.txt`
