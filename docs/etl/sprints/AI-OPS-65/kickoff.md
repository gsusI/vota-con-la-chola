# AI-OPS-65 Kickoff

Date:
- 2026-02-23

Objective:
- Publish initiative-doc actionable-tail contract+digest directly in explorer-sources status payload and expose it in the static/public UI card.

Primary lane (controllable):
- Explorer-sources parity hardening (`/api/sources/status` == `docs/gh-pages/explorer-sources/data/status.json`) for the Senate tail signal.

Acceptance gates:
- `scripts/graph_ui_server.py` emits `initdoc_actionable_tail` (`contract` + `digest`) in `build_sources_status_payload`.
- `ui/graph/explorer-sources.html` renders card `Iniciativas Senado (tail)` from `initdoc_actionable_tail.digest`.
- `tests/test_graph_ui_server_initdoc_tail.py` validates:
  - `status=failed` with actionable queue open
  - `status=ok` when missing rows are only redundant.
- CI `initdoc-actionable-tail-contract` includes the new payload test suite.
- `just explorer-gh-pages-build` regenerates static explorer payload/UI with the new block.

DoD:
- Unit tests + py_compile pass.
- Real status export evidence captured.
- GH Pages build evidence captured.
- Tracker/docs/sprint index updated.
