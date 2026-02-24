# AI-OPS-68 Report: Initdoc Tail Compact-Window Digest

Date:
- 2026-02-23

Objective:
- Add a compact digest layer over initdoc heartbeat compaction-window parity and publish it in API/UI/CI contracts.

What shipped:
- New digest reporter:
  - `scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.py`
- API payload integration:
  - `initdoc_actionable_tail.heartbeat_compaction_window_digest` in `scripts/graph_ui_server.py`
- UI integration:
  - `/explorer-sources` card now renders `compact-digest` status and risk summary (`ui/graph/explorer-sources.html`)
- Ops wrappers:
  - `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest`
  - `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest`
- CI hardening:
  - `initdoc-actionable-tail-contract` now exercises strict fail/pass for compact-window digest.

Validation:
- Unit tests passed:
  - `docs/etl/sprints/AI-OPS-68/evidence/python_unittest_initdoc_tail_compaction_window_digest_20260223T083515Z.txt`
- Compile checks passed:
  - `docs/etl/sprints/AI-OPS-68/evidence/py_compile_initdoc_tail_compaction_window_digest_20260223T083515Z.txt`
- Strict just check passed:
  - `docs/etl/sprints/AI-OPS-68/evidence/initdoc_actionable_tail_compact_window_digest_check_20260223T083524Z.txt`

Live status snapshot:
- `digest_status=ok`
- `heartbeat_window_status=ok`
- `heartbeat_compaction_window_status=ok`
- `heartbeat_compaction_window_digest_status=ok`
- `heartbeat_compaction_window_digest_risk_level=green`
- Evidence:
  - `docs/etl/sprints/AI-OPS-68/evidence/explorer_sources_initdoc_tail_compact_window_digest_summary_20260223T083535Z.json`

Implementation markers:
- `docs/etl/sprints/AI-OPS-68/evidence/initdoc_tail_compact_window_digest_markers_20260223T083607Z.txt`
