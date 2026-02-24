# Citizen Mobile Observability v1 (AI-OPS-83)

Date:
- 2026-02-23

Goal:
- Make `/citizen` mobile interaction latency measurable with an explicit percentile gate (`p50/p90`) and reproducible strict checks.

What shipped:
- `/citizen` latency sampling instrumentation in `ui/citizen/index.html`:
  - new markers/constants: `MOBILE_LATENCY_OBS_VERSION`, `MOBILE_LATENCY_STORAGE_KEY`
  - input-to-render sampling hooks:
    - `markInputLatencySampleStart(source)`
    - `commitInputLatencySample(trigger)`
  - local debug/export API (browser console):
    - `window.__vclcMobileLatencySummary()`
    - `window.__vclcMobileLatencyExport()`
    - `window.__vclcMobileLatencyClear()`
  - wired to key input paths:
    - concern/topic search inputs
    - stance filter change
    - party sort change
- New machine-readable observability report:
  - `scripts/report_citizen_mobile_observability.py`
  - supports telemetry summary JSON and raw events JSONL
  - outputs `status` (`ok|degraded|failed`) with strict gates and reasons
- New tests:
  - `tests/test_citizen_mobile_observability_ui_contract.js`
  - `tests/test_report_citizen_mobile_observability.py`
- Updated mobile-performance contract to require observability markers:
  - `scripts/report_citizen_mobile_performance_budget.py`
  - `tests/test_citizen_mobile_performance_ui_contract.js`
  - `tests/test_report_citizen_mobile_performance_budget.py`
- New deterministic fixture:
  - `tests/fixtures/citizen_mobile_latency_events_sample.jsonl`
- New `just` targets:
  - `just citizen-test-mobile-observability`
  - `just citizen-report-mobile-observability`
  - `just citizen-check-mobile-observability`
  - plus inclusion in `just citizen-release-regression-suite`

Validation:
- `node --test tests/test_citizen_mobile_observability_ui_contract.js`
- `python3 -m unittest tests/test_report_citizen_mobile_observability.py`
- `just citizen-test-mobile-observability`
- `just citizen-report-mobile-observability`
- `just citizen-check-mobile-observability`
- regression safety:
  - `just citizen-test-mobile-performance`
  - `just citizen-check-mobile-performance-budget`
  - `just citizen-release-regression-suite`
  - `just explorer-gh-pages-build`
  - `just citizen-check-release-hardening`

Strict observability result:
- `status=ok`
- `sample_count=30`
- `input_to_render_p50_ms=147.5`
- `input_to_render_p90_ms=423.0`
- thresholds:
  - `min_samples=20`
  - `max_input_to_render_p50_ms=180.0`
  - `max_input_to_render_p90_ms=450.0`

Evidence:
- `docs/etl/sprints/AI-OPS-83/evidence/citizen_mobile_observability_contract_summary_20260223T120029Z.json`
- `docs/etl/sprints/AI-OPS-83/evidence/citizen_mobile_observability_contract_markers_20260223T120029Z.txt`
- `docs/etl/sprints/AI-OPS-83/evidence/just_citizen_check_mobile_observability_20260223T120027Z.txt`
- `docs/etl/sprints/AI-OPS-83/evidence/just_citizen_release_regression_suite_20260223T120027Z.txt`
- `docs/etl/sprints/AI-OPS-83/evidence/just_explorer_gh_pages_build_20260223T120337Z.txt`
- `docs/etl/sprints/AI-OPS-83/evidence/just_citizen_check_release_hardening_20260223T120337Z.txt`
