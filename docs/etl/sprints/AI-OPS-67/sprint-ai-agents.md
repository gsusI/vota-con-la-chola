# AI-OPS-67 Prompt Pack

Objective:
- Harden the initdoc actionable-tail trend lane with bounded retention and parity checks so long-running monitoring remains reproducible and compact.

Acceptance gates:
- New reporters:
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction.py`
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py`
- New just wrappers:
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat-compact`
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat-compact-window`
- Status payload:
  - `build_sources_status_payload` includes `initdoc_actionable_tail.heartbeat_compaction_window`.
- UI:
  - `/explorer-sources` card shows compacted parity state (`compact OK|DEGRADED|FAILED`).
- CI:
  - `initdoc-actionable-tail-contract` validates compaction + compaction-window strict fail/pass.

Status update (2026-02-23):
- Implemented, validated, and documented with evidence artifacts under `docs/etl/sprints/AI-OPS-67/evidence`.
