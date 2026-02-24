# Citizen Mobile Observability Heartbeat Trend v1 (AI-OPS-90)

Date:
- 2026-02-23

Goal:
- Add a machine-readable trend lane for mobile latency so `/citizen` `p90` stability can be tracked over time (append-only heartbeat + strict last-N SLO window).

What shipped:
- New heartbeat reporter:
  - `scripts/report_citizen_mobile_observability_heartbeat.py`
  - reads latest mobile observability digest and appends deduped JSONL entries
  - emits status + strict fail reasons for failed runs
- New window reporter:
  - `scripts/report_citizen_mobile_observability_heartbeat_window.py`
  - computes last-N trend with strict checks for:
    - failed/degraded counts and rates
    - p90 threshold violation counts and rates
    - latest-run failed/p90 violation guards
- New tests:
  - `tests/test_report_citizen_mobile_observability_heartbeat.py`
  - `tests/test_report_citizen_mobile_observability_heartbeat_window.py`
- New `just` lanes:
  - `just citizen-test-mobile-observability-heartbeat`
  - `just citizen-report-mobile-observability-heartbeat`
  - `just citizen-check-mobile-observability-heartbeat`
  - `just citizen-report-mobile-observability-heartbeat-window`
  - `just citizen-check-mobile-observability-heartbeat-window`
  - lane added to `just citizen-release-regression-suite`

Validation:
- `just citizen-test-mobile-observability-heartbeat`
- `just citizen-report-mobile-observability`
- `just citizen-check-mobile-observability`
- `just citizen-report-mobile-observability-heartbeat`
- `just citizen-check-mobile-observability-heartbeat`
- `just citizen-report-mobile-observability-heartbeat-window`
- `just citizen-check-mobile-observability-heartbeat-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict trend result:
- `heartbeat_status=ok`
- `window_status=ok`
- `sample_count=30`
- `input_to_render_p90_ms=423.0`
- `max_input_to_render_p90_ms=450.0`
- `p90_margin_ms=27.0`
- `window_entries_in_window=1`
- `window_p90_threshold_violations_in_window=0`

Evidence:
- `docs/etl/sprints/AI-OPS-90/evidence/citizen_mobile_observability_heartbeat_latest.json`
- `docs/etl/sprints/AI-OPS-90/evidence/citizen_mobile_observability_heartbeat_window_latest.json`
- `docs/etl/sprints/AI-OPS-90/evidence/citizen_mobile_observability_heartbeat_20260223T131406Z.json`
- `docs/etl/sprints/AI-OPS-90/evidence/citizen_mobile_observability_heartbeat_window_20260223T131406Z.json`
- `docs/etl/sprints/AI-OPS-90/evidence/citizen_mobile_observability_heartbeat_summary_20260223T131406Z.json`
- `docs/etl/sprints/AI-OPS-90/evidence/just_citizen_test_mobile_observability_heartbeat_20260223T131406Z.txt`
- `docs/etl/sprints/AI-OPS-90/evidence/just_citizen_check_mobile_observability_heartbeat_20260223T131406Z.txt`
- `docs/etl/sprints/AI-OPS-90/evidence/just_citizen_check_mobile_observability_heartbeat_window_20260223T131406Z.txt`
- `docs/etl/sprints/AI-OPS-90/evidence/just_citizen_release_regression_suite_20260223T131406Z.txt`
- `docs/etl/sprints/AI-OPS-90/evidence/just_explorer_gh_pages_build_20260223T131406Z.txt`
