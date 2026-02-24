# Citizen Release-Trace Heartbeat Retention v1 (AI-OPS-102)

Date:
- 2026-02-23

Goal:
- Keep the release-trace heartbeat lane bounded over time while preserving freshness/failure incidents and validating compacted parity against raw history.

What shipped:
- New compaction reporter:
  - `scripts/report_citizen_release_trace_digest_heartbeat_compaction.py`
  - compacts heartbeat history with deterministic cadence (`recent/mid/old`) while preserving anchors (`oldest/latest`) and incidents.
  - incident-preservation set:
    - `failed` rows
    - `degraded` rows
    - strict rows (`strict_fail_count > 0` / `strict_fail_reasons`)
    - stale rows (`stale_detected=true` / stale inference)
    - malformed rows
- New compaction-window parity reporter:
  - `scripts/report_citizen_release_trace_digest_heartbeat_compaction_window.py`
  - compares raw vs compacted heartbeat in `last N`.
  - enforces strict checks for:
    - latest-row presence in compacted history
    - incident parity (`failed`, `degraded`, strict rows, stale rows, malformed rows)
- New tests:
  - `tests/test_report_citizen_release_trace_digest_heartbeat_compaction.py`
  - `tests/test_report_citizen_release_trace_digest_heartbeat_compaction_window.py`
- `just` wiring:
  - new vars: `citizen_release_trace_heartbeat_compact_*`
  - new lanes:
    - `just citizen-report-release-trace-heartbeat-compact`
    - `just citizen-check-release-trace-heartbeat-compact`
    - `just citizen-report-release-trace-heartbeat-compact-window`
    - `just citizen-check-release-trace-heartbeat-compact-window`
  - `just citizen-test-release-trace-heartbeat` now includes compaction + parity tests.

Validation:
- `python3 -m py_compile scripts/report_citizen_release_trace_digest_heartbeat_compaction.py scripts/report_citizen_release_trace_digest_heartbeat_compaction_window.py`
- `just citizen-test-release-trace-heartbeat`
- `just citizen-check-release-trace-heartbeat`
- `just citizen-check-release-trace-heartbeat-window`
- `just citizen-check-release-trace-heartbeat-compact`
- `just citizen-check-release-trace-heartbeat-compact-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict run result (`20260223T151731Z`):
- Compaction strict check: PASS (`strict_fail_reasons=[]`, `entries_total=1`, `selected_entries=1`, `dropped_entries=0`, status `degraded` due tiny history)
- Compaction-window strict check: PASS (`status=ok`, `window_raw_entries=1`, `latest_present_ok=true`, `incident_missing_in_compacted=0`, `stale_rows_missing_in_compacted=0`)

Evidence:
- `docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_compaction_latest.json`
- `docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_compaction_window_latest.json`
- `docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_compaction_20260223T151731Z.json`
- `docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_compaction_window_20260223T151731Z.json`
- `docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_20260223T151731Z.json`
- `docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_window_20260223T151731Z.json`
- `docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_20260223T151731Z.jsonl`
- `docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_compacted_20260223T151731Z.jsonl`
- `docs/etl/sprints/AI-OPS-102/evidence/just_citizen_test_release_trace_heartbeat_20260223T151731Z.txt`
- `docs/etl/sprints/AI-OPS-102/evidence/just_citizen_check_release_trace_heartbeat_20260223T151731Z.txt`
- `docs/etl/sprints/AI-OPS-102/evidence/just_citizen_check_release_trace_heartbeat_window_20260223T151731Z.txt`
- `docs/etl/sprints/AI-OPS-102/evidence/just_citizen_check_release_trace_heartbeat_compact_20260223T151731Z.txt`
- `docs/etl/sprints/AI-OPS-102/evidence/just_citizen_check_release_trace_heartbeat_compact_window_20260223T151731Z.txt`
- `docs/etl/sprints/AI-OPS-102/evidence/just_citizen_release_regression_suite_20260223T151731Z.txt`
- `docs/etl/sprints/AI-OPS-102/evidence/just_explorer_gh_pages_build_20260223T151731Z.txt`
