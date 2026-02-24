# AI-OPS-72 Kickoff

Date:
- 2026-02-23

Objective:
- Add a deterministic KPI contract for `/citizen` product progression (Scenario A), using existing static artifacts and optional telemetry.

Primary lane (controllable):
- Product observability contract (`unknown_rate`, `time_to_first_answer_seconds`, `drilldown_click_rate`) with strict machine-readable checks.

Acceptance gates:
- G1 Reporter implemented with explicit status contract (`ok|degraded|failed`).
- G2 Strict modes implemented:
  - `--strict` (fail only on failed)
  - `--strict-require-complete` (fail on failed or degraded)
- G3 Unit tests cover pass/degraded/fail behavior.
- G4 `just` wrappers available for report/check flows.
- G5 Sprint evidence artifact generated under `docs/etl/sprints/AI-OPS-72/evidence/`.

DoD:
- `python3 -m unittest tests/test_report_citizen_product_kpis.py` passes.
- `python3 -m py_compile scripts/report_citizen_product_kpis.py` passes.
- KPI artifact generated and linked in sprint closeout/report.
