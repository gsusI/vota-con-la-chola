# AI-OPS-69 Prompt Pack

Objective:
- Add a heartbeat lane and strict last-N window for the initdoc compact-window digest so alert polling has a durable NDJSON trend contract.

Acceptance gates:
- New reporters:
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.py`
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_window.py`
- New just wrappers:
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat`
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-window`
- Status payload:
  - `build_sources_status_payload` includes `initdoc_actionable_tail.heartbeat_compaction_window_digest_heartbeat_window`.
- UI:
  - `/explorer-sources` card shows compact-digest trend status.
- CI:
  - `initdoc-actionable-tail-contract` validates strict fail/pass for digest-heartbeat and digest-heartbeat-window.

Status update (2026-02-23):
- Implemented, validated, and documented with evidence artifacts under `docs/etl/sprints/AI-OPS-69/evidence`.
