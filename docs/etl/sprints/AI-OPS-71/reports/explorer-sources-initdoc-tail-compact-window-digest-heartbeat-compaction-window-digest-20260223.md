# AI-OPS-71 Report: Initdoc Tail cd-Compact Digest

Date:
- 2026-02-23

Objective:
- Add a compact digest contract for the initdoc `cd-compact` parity lane and expose it in sources status/UI.

What shipped:
- New reporter:
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
- API payload integration:
  - `initdoc_actionable_tail.heartbeat_compaction_window_digest_heartbeat_compaction_window_digest` in `scripts/graph_ui_server.py`.
- UI integration:
  - `/explorer-sources` card adds `cd-digest` status for this lane (`ui/graph/explorer-sources.html`).
- Ops wrappers:
  - `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window-digest`
  - `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window-digest`
- CI hardening:
  - `initdoc-actionable-tail-contract` now exercises strict fail/pass for this digest.

Validation:
- Unit tests passed:
  - `docs/etl/sprints/AI-OPS-71/evidence/python_unittest_initdoc_tail_compact_window_digest_heartbeat_compaction_window_digest_20260223T090432Z.txt`
- Compile checks passed:
  - `docs/etl/sprints/AI-OPS-71/evidence/py_compile_initdoc_tail_compact_window_digest_heartbeat_compaction_window_digest_20260223T090432Z.txt`
- Strict just check passed:
  - `docs/etl/sprints/AI-OPS-71/evidence/initdoc_actionable_tail_compact_window_digest_heartbeat_compaction_window_digest_check_20260223T090432Z.txt`

Live status snapshot:
- `digest_status=ok`
- `heartbeat_window_status=ok`
- `heartbeat_compaction_window_status=ok`
- `heartbeat_compaction_window_digest_status=ok`
- `heartbeat_compaction_window_digest_heartbeat_window_status=ok`
- `heartbeat_compaction_window_digest_heartbeat_compaction_window_status=ok`
- `heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_status=ok`
- `heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_risk_level=green`
- Evidence:
  - `docs/etl/sprints/AI-OPS-71/evidence/explorer_sources_initdoc_tail_compact_window_digest_heartbeat_compaction_window_digest_summary_20260223T090432Z.json`

Implementation markers:
- `docs/etl/sprints/AI-OPS-71/evidence/initdoc_tail_compact_window_digest_heartbeat_compaction_window_digest_markers_20260223T090432Z.txt`
