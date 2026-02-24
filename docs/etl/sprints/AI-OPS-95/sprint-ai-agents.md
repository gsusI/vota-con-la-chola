# AI-OPS-95 Prompt Pack

Objective:
- Ship mobile observability heartbeat retention v1 so `/citizen` keeps a bounded heartbeat history while preserving incidents and enforcing strict raw-vs-compacted parity checks.

Acceptance gates:
- Add incident-preserving compaction reporter for mobile observability heartbeat (`scripts/report_citizen_mobile_observability_heartbeat_compaction.py`).
- Add strict raw-vs-compacted last-N parity reporter for mobile heartbeat compaction (`scripts/report_citizen_mobile_observability_heartbeat_compaction_window.py`).
- Preserve incident classes in compaction/parity (`failed`, `degraded`, strict rows, malformed rows, and p90 threshold violations).
- Add deterministic tests for compaction + parity window strict behavior.
- Wire `just` report/check/test lanes and include heartbeat lane in `citizen-release-regression-suite`.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`compaction_status=degraded` on small history, `compaction_window_status=ok`, `strict_fail_reasons=[]`).
