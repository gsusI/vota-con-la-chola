# AI-OPS-102 Prompt Pack

Objective:
- Ship release-trace heartbeat retention v1 so `/citizen` release freshness telemetry has incident-preserving compaction and strict raw-vs-compacted last-N parity coverage.

Acceptance gates:
- Add release-trace heartbeat compaction reporter (`scripts/report_citizen_release_trace_digest_heartbeat_compaction.py`).
- Add release-trace heartbeat compaction-window parity reporter (`scripts/report_citizen_release_trace_digest_heartbeat_compaction_window.py`).
- Preserve incidents (`failed`, `degraded`, strict rows, stale rows, malformed rows) across compaction.
- Add deterministic tests for compaction and compaction-window strict behavior.
- Wire new `just` report/check lanes and include compaction tests in `citizen-test-release-trace-heartbeat`.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`compaction_status=degraded` with `strict_fail_reasons=[]` on tiny history, `compaction_window_status=ok`, `incident_missing_in_compacted=0`, `stale_rows_missing_in_compacted=0`).
