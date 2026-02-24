# AI-OPS-70 Report: Initdoc Tail Compact-Window Digest Heartbeat Compaction

Date:
- 2026-02-23

Objective:
- Add retention and parity hardening for the initdoc compact-window digest heartbeat lane, and surface the `cd-compact` state in sources status/UI.

What shipped:
- New reporters:
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py`
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
- Runtime-path hardening:
  - wrappers now support both import contexts (`python3 scripts/...` and module imports used by tests/server).
- API payload integration:
  - `initdoc_actionable_tail.heartbeat_compaction_window_digest_heartbeat_compaction_window` in `scripts/graph_ui_server.py`.
- UI integration:
  - `/explorer-sources` card adds `cd-compact` status for this lane (`ui/graph/explorer-sources.html`).
- Ops wrappers:
  - `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact`
  - `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact`
  - `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window`
  - `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window`
- CI hardening:
  - `initdoc-actionable-tail-contract` now exercises strict fail/pass for digest-heartbeat compaction + compaction-window.

Validation:
- Unit tests passed:
  - `docs/etl/sprints/AI-OPS-70/evidence/python_unittest_initdoc_tail_compact_window_digest_heartbeat_compaction_20260223T085546Z.txt`
- Compile checks passed:
  - `docs/etl/sprints/AI-OPS-70/evidence/py_compile_initdoc_tail_compact_window_digest_heartbeat_compaction_20260223T085546Z.txt`
- Strict just checks passed:
  - `docs/etl/sprints/AI-OPS-70/evidence/initdoc_actionable_tail_compact_window_digest_heartbeat_compaction_check_20260223T085546Z.txt`
  - `docs/etl/sprints/AI-OPS-70/evidence/initdoc_actionable_tail_compact_window_digest_heartbeat_compaction_window_check_20260223T085546Z.txt`

Live status snapshot:
- `digest_status=ok`
- `heartbeat_window_status=ok`
- `heartbeat_compaction_window_status=ok`
- `heartbeat_compaction_window_digest_status=ok`
- `heartbeat_compaction_window_digest_heartbeat_window_status=ok`
- `heartbeat_compaction_window_digest_heartbeat_compaction_window_status=ok`
- Evidence:
  - `docs/etl/sprints/AI-OPS-70/evidence/explorer_sources_initdoc_tail_compact_window_digest_heartbeat_compaction_summary_20260223T085546Z.json`

Implementation markers:
- `docs/etl/sprints/AI-OPS-70/evidence/initdoc_tail_compact_window_digest_heartbeat_compaction_markers_20260223T085546Z.txt`
