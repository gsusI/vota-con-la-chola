# AI-OPS-68 Prompt Pack

Objective:
- Add a compact parity digest for the initdoc actionable-tail compaction window so polling/alerting and explorer payloads can consume a single machine-readable `status/risk` contract.

Acceptance gates:
- New reporter:
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.py`
- New just wrappers:
  - `parl-report/check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest`
- Status payload:
  - `build_sources_status_payload` includes `initdoc_actionable_tail.heartbeat_compaction_window_digest`.
- UI:
  - `/explorer-sources` card shows compact-digest status in addition to trend/compact parity.
- CI:
  - `initdoc-actionable-tail-contract` validates strict fail/pass for compaction-window digest.

Status update (2026-02-23):
- Implemented, validated, and documented with evidence artifacts under `docs/etl/sprints/AI-OPS-68/evidence`.
