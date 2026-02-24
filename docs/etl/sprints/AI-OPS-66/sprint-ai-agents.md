# AI-OPS-66 Prompt Pack

Objective:
- Add a reproducible trend lane for the initiative-doc actionable tail so `/explorer-sources` can show last-N health without CI log spelunking.

Acceptance gates:
- New reporters:
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat.py`
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_window.py`
- New just wrappers:
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat`
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat-window`
- Status payload:
  - `build_sources_status_payload` embeds `initdoc_actionable_tail.heartbeat_window`.
- UI:
  - `ui/graph/explorer-sources.html` card shows trend summary (`failed/degraded/latest`, last-N).
- CI:
  - `initdoc-actionable-tail-contract` job validates heartbeat + window fail/pass artifacts.

Status update (2026-02-23):
- Implemented end-to-end and validated on unit tests, strict checks, explorer snapshot export, GH Pages build, and tracker gate.
