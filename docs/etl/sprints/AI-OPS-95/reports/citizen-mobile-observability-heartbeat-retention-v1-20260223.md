# Citizen Mobile Observability Heartbeat Retention v1 (AI-OPS-95)

Date:
- 2026-02-23

Goal:
- Keep the mobile observability heartbeat lane bounded over time while preserving audit-critical incidents and validating compacted parity against raw history.

What shipped:
- New parity reporter:
  - `scripts/report_citizen_mobile_observability_heartbeat_compaction_window.py`
  - compares raw vs compacted heartbeat in last-N window
  - enforces strict checks for latest-row and incident preservation (`failed`, `degraded`, strict rows, malformed rows, p90 threshold violations)
- Compaction reporter hardening:
  - `scripts/report_citizen_mobile_observability_heartbeat_compaction.py`
  - incident set now explicitly includes p90-threshold violations
- New tests:
  - `tests/test_report_citizen_mobile_observability_heartbeat_compaction.py`
  - `tests/test_report_citizen_mobile_observability_heartbeat_compaction_window.py`
- `just` wiring:
  - new vars for compacted path/strategy/out and compact-window controls
  - new lanes:
    - `just citizen-report-mobile-observability-heartbeat-compact`
    - `just citizen-check-mobile-observability-heartbeat-compact`
    - `just citizen-report-mobile-observability-heartbeat-compact-window`
    - `just citizen-check-mobile-observability-heartbeat-compact-window`
  - `just citizen-test-mobile-observability-heartbeat` now includes compaction + parity tests
  - lane added to `just citizen-release-regression-suite`

Validation:
- `just citizen-test-mobile-observability-heartbeat`
- `just citizen-check-mobile-observability-heartbeat-compact`
- `just citizen-check-mobile-observability-heartbeat-compact-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict run result:
- Compaction strict check: PASS (`strict_fail_reasons=[]`, `entries_total=1`, `selected_entries=1`, `dropped_entries=0`, status `degraded` due tiny history)
- Compaction-window strict check: PASS (`status=ok`, `window_raw_entries=1`, `latest_present_ok=true`, `incident_missing_in_compacted=0`, `p90_violations_missing_in_compacted=0`)

Evidence:
- `docs/etl/sprints/AI-OPS-95/evidence/citizen_mobile_observability_heartbeat_compaction_latest.json`
- `docs/etl/sprints/AI-OPS-95/evidence/citizen_mobile_observability_heartbeat_compaction_window_latest.json`
- `docs/etl/sprints/AI-OPS-95/evidence/citizen_mobile_observability_heartbeat_compaction_20260223T140552Z.json`
- `docs/etl/sprints/AI-OPS-95/evidence/citizen_mobile_observability_heartbeat_compaction_window_20260223T140552Z.json`
- `docs/etl/sprints/AI-OPS-95/evidence/just_citizen_test_mobile_observability_heartbeat_20260223T140552Z.txt`
- `docs/etl/sprints/AI-OPS-95/evidence/just_citizen_check_mobile_observability_heartbeat_compact_20260223T140552Z.txt`
- `docs/etl/sprints/AI-OPS-95/evidence/just_citizen_check_mobile_observability_heartbeat_compact_window_20260223T140552Z.txt`
- `docs/etl/sprints/AI-OPS-95/evidence/just_citizen_release_regression_suite_20260223T140552Z.txt`
- `docs/etl/sprints/AI-OPS-95/evidence/just_explorer_gh_pages_build_20260223T140552Z.txt`
