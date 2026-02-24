# Citizen Mobile Performance Pass (AI-OPS-76)

Date:
- 2026-02-23

Goal:
- Ship a controllable, visible mobile performance delta and make it enforceable through strict local contracts.

What shipped:
- Mobile/perf UI pass in `ui/citizen/index.html`:
  - render-cost hints for long lists/cards via `content-visibility: auto` + `contain-intrinsic-size`
  - tighter mobile layout/tap-target rules in `@media (max-width: 760px)`
  - reduced-motion guard (`@media (prefers-reduced-motion: reduce)`)
  - interaction latency contract with `SEARCH_INPUT_DEBOUNCE_MS=120` and compare render coalescing (`scheduleRenderCompare`, `RENDER_COMPARE_SCHEDULE="raf"`)
  - debounced search input handlers for concern/topic filters
- New machine-readable budget contract script:
  - `scripts/report_citizen_mobile_performance_budget.py`
  - checks UI HTML bytes, JS companion assets total bytes, snapshot bytes, and required interaction markers
  - strict mode returns non-zero when failed (`--strict`)
- New tests and just targets:
  - `tests/test_citizen_mobile_performance_ui_contract.js`
  - `tests/test_report_citizen_mobile_performance_budget.py`
  - `just citizen-test-mobile-performance`
  - `just citizen-report-mobile-performance-budget`
  - `just citizen-check-mobile-performance-budget`

Budget result (current run):
- `ui_html_bytes=176329` (max `220000`)
- `ui_assets_total_bytes=27961` (max `60000`)
- `snapshot_bytes=950181` (max `5000000`)
- `interaction_markers_missing=[]`
- status: `ok`

Validation:
- `just citizen-test-mobile-performance`
- `just citizen-check-mobile-performance-budget`
- `just citizen-test-unknown-explainability` (regression)
- `just citizen-test-first-answer-accelerator` (regression)
- `node --check` inline script extraction
- `python3 -m py_compile scripts/report_citizen_mobile_performance_budget.py`

Evidence:
- `docs/etl/sprints/AI-OPS-76/evidence/citizen_mobile_performance_contract_summary_20260223T110016Z.json`
- `docs/etl/sprints/AI-OPS-76/evidence/citizen_mobile_performance_budget_20260223T110016Z.json`
- `docs/etl/sprints/AI-OPS-76/evidence/citizen_mobile_performance_contract_markers_20260223T110016Z.txt`
