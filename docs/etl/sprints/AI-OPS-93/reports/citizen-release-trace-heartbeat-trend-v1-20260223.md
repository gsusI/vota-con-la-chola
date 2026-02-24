# Citizen Release-Trace Heartbeat Trend v1 (AI-OPS-93)

Date:
- 2026-02-23

Goal:
- Add a machine-readable trend lane for release-trace freshness so stale/failed regressions can be detected without reading full release artifacts.

What shipped:
- New heartbeat reporter:
  - `scripts/report_citizen_release_trace_digest_heartbeat.py`
  - reads latest release-trace digest and appends deduped JSONL entries
  - emits strict status and fail reasons for invalid/failed digests
- New window reporter:
  - `scripts/report_citizen_release_trace_digest_heartbeat_window.py`
  - computes strict last-N checks for:
    - failed/degraded counts and rates
    - stale counts and rates
    - latest-run failed/freshness guards
- New tests:
  - `tests/test_report_citizen_release_trace_digest_heartbeat.py`
  - `tests/test_report_citizen_release_trace_digest_heartbeat_window.py`
- New `just` lanes:
  - `just citizen-test-release-trace-heartbeat`
  - `just citizen-report-release-trace-heartbeat`
  - `just citizen-check-release-trace-heartbeat`
  - `just citizen-report-release-trace-heartbeat-window`
  - `just citizen-check-release-trace-heartbeat-window`
  - lane added to `just citizen-release-regression-suite`

Validation:
- `just citizen-test-release-trace-digest`
- `just citizen-test-release-trace-heartbeat`
- `just citizen-report-release-trace-heartbeat`
- `just citizen-check-release-trace-heartbeat`
- `just citizen-report-release-trace-heartbeat-window`
- `just citizen-check-release-trace-heartbeat-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict trend result:
- `heartbeat_status=ok`
- `window_status=ok`
- `entries_in_window=1`
- `failed_in_window=0`
- `degraded_in_window=0`
- `stale_in_window=0`
- `latest_freshness_within_sla=true`

Evidence:
- `docs/etl/sprints/AI-OPS-93/evidence/citizen_release_trace_digest_heartbeat_latest.json`
- `docs/etl/sprints/AI-OPS-93/evidence/citizen_release_trace_digest_heartbeat_window_latest.json`
- `docs/etl/sprints/AI-OPS-93/evidence/citizen_release_trace_digest_heartbeat_20260223T134242Z.json`
- `docs/etl/sprints/AI-OPS-93/evidence/citizen_release_trace_digest_heartbeat_window_20260223T134242Z.json`
- `docs/etl/sprints/AI-OPS-93/evidence/citizen_release_trace_digest_heartbeat_summary_20260223T134242Z.json`
- `docs/etl/sprints/AI-OPS-93/evidence/citizen_release_trace_digest_heartbeat_window_summary_20260223T134242Z.json`
- `docs/etl/sprints/AI-OPS-93/evidence/just_citizen_test_release_trace_heartbeat_20260223T134242Z.txt`
- `docs/etl/sprints/AI-OPS-93/evidence/just_citizen_check_release_trace_heartbeat_20260223T134242Z.txt`
- `docs/etl/sprints/AI-OPS-93/evidence/just_citizen_check_release_trace_heartbeat_window_20260223T134242Z.txt`
- `docs/etl/sprints/AI-OPS-93/evidence/just_citizen_release_regression_suite_20260223T134242Z.txt`
- `docs/etl/sprints/AI-OPS-93/evidence/just_explorer_gh_pages_build_20260223T134242Z.txt`
