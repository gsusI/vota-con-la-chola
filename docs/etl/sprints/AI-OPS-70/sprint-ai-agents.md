# AI-OPS-70 Prompt Pack

Objective:
- Add retention-safe compaction + strict last-N parity for the initdoc compact-window digest heartbeat lane (`cd-trend`) so polling keeps a bounded `cd-compact` contract.

Acceptance gates:
- New reporters:
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py`
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
- New just wrappers:
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact`
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window`
- Status payload:
  - `build_sources_status_payload` includes `initdoc_actionable_tail.heartbeat_compaction_window_digest_heartbeat_compaction_window`.
- UI:
  - `/explorer-sources` card shows `cd-compact` status for this lane.
- CI:
  - `initdoc-actionable-tail-contract` validates strict fail/pass for digest-heartbeat compaction + compaction-window.

Status update (2026-02-23):
- Implemented, validated, and documented with evidence artifacts under `docs/etl/sprints/AI-OPS-70/evidence`.
