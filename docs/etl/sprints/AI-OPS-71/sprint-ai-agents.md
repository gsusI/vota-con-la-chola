# AI-OPS-71 Prompt Pack

Objective:
- Add a compact digest contract for the initdoc `cd-compact` parity lane so alert polling can consume a single `ok|degraded|failed` artifact (with `risk_level`) instead of full parity payloads.

Acceptance gates:
- New reporter:
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
- New just wrappers:
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window-digest`
- Status payload:
  - `build_sources_status_payload` includes `initdoc_actionable_tail.heartbeat_compaction_window_digest_heartbeat_compaction_window_digest`.
- UI:
  - `/explorer-sources` card shows `cd-digest` status for this lane.
- CI:
  - `initdoc-actionable-tail-contract` validates strict fail/pass for the new compaction-window digest.

Status update (2026-02-23):
- Implemented, validated, and documented with evidence artifacts under `docs/etl/sprints/AI-OPS-71/evidence`.
