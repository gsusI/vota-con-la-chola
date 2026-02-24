# AI-OPS-72 Report: Citizen Product KPI Contract v1

Date:
- 2026-02-23

Objective:
- Implement a reproducible KPI artifact for Scenario A to track first-answer speed, uncertainty, and drill-down usage.

What shipped:
- New reporter: `scripts/report_citizen_product_kpis.py`
  - Inputs:
    - `--snapshot <citizen.json>`
    - optional `--telemetry-json <summary.json>`
    - optional `--telemetry-events-jsonl <events.jsonl>`
  - Outputs:
    - `metrics.unknown_rate`
    - `metrics.time_to_first_answer_seconds`
    - `metrics.drilldown_click_rate`
    - `status` (`ok|degraded|failed`)
- New tests:
  - `tests/test_report_citizen_product_kpis.py`
- Ops wrappers in `justfile`:
  - `just citizen-report-product-kpis`
  - `just citizen-check-product-kpis`
  - `just citizen-check-product-kpis-complete`
- ETL docs update:
  - `docs/etl/README.md`

Validation:
- Unit tests and compile check recorded under sprint evidence.
  - `docs/etl/sprints/AI-OPS-72/evidence/python_unittest_citizen_product_kpis_20260223T102951Z.txt`
  - `docs/etl/sprints/AI-OPS-72/evidence/py_compile_citizen_product_kpis_20260223T102951Z.txt`
  - `docs/etl/sprints/AI-OPS-72/evidence/citizen_product_kpis_check_20260223T102951Z.txt`
  - `docs/etl/sprints/AI-OPS-72/evidence/citizen_product_kpis_check_complete_20260223T102951Z.txt`

Current artifact status:
- `docs/etl/sprints/AI-OPS-72/evidence/citizen_product_kpis_latest.json`
- Latest metrics snapshot:
  - `status=degraded`
  - `unknown_rate=0.175676`
  - `time_to_first_answer_seconds=null`
  - `drilldown_click_rate=null`
  - `missing_metrics=[time_to_first_answer_seconds, drilldown_click_rate]`
  - `unknown_rate_within_threshold=true`
