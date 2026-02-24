# AI-OPS-65 Prompt Pack

Objective:
- Close the loop between initiative-doc actionable-tail contracts and the public status surface by embedding that signal in explorer-sources payload/UI.

Acceptance gates:
- `build_sources_status_payload` includes:
  - `initdoc_actionable_tail.contract`
  - `initdoc_actionable_tail.digest`
- `/explorer-sources` global KPI card shows:
  - actionable missing count
  - digest status pill (`OK|DEGRADED|FAILED`)
  - redundant/total missing counts.
- Static export parity:
  - `scripts/export_explorer_sources_snapshot.py` output contains `initdoc_actionable_tail`.
  - `docs/gh-pages/explorer-sources/index.html` includes the new card render path.
- Regression tests:
  - `tests/test_graph_ui_server_initdoc_tail.py`
  - CI workflow includes this test in `initdoc-actionable-tail-contract`.

Status update (2026-02-23):
- Implemented end-to-end and validated on fixture tests + real DB export + GH Pages rebuild.
