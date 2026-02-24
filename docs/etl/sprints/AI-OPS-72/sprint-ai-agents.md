# AI-OPS-72 Prompt Pack

Objective:
- Ship Citizen KPI contract v1 with a reproducible artifact that tracks `unknown_rate`, `time_to_first_answer_seconds`, and `drilldown_click_rate`.

Acceptance gates:
- New reporter script: `scripts/report_citizen_product_kpis.py`.
- Test coverage for pass/degraded/fail paths: `tests/test_report_citizen_product_kpis.py`.
- Ops wrappers in `justfile`:
  - `citizen-report-product-kpis`
  - `citizen-check-product-kpis`
  - `citizen-check-product-kpis-complete`
- Reproducible evidence artifact written under sprint evidence.
- Docs updated so future collaborators know the contract and commands.

Status update (2026-02-23):
- Implemented and validated. KPI artifact now reports explicit `ok|degraded|failed` status, with optional telemetry inputs and strict gates.
