# AI-OPS-66 Kickoff

Date:
- 2026-02-23

Objective:
- Add heartbeat + window trend observability for `initdoc_actionable_tail` and surface it in explorer-sources/public status.

Primary lane (controllable):
- Operational signal hardening for Senate initiative-doc tail (`actionable_missing`) without dependence on external source behavior.

Acceptance gates:
- `report_initdoc_actionable_tail_digest_heartbeat.py` appends deduped JSONL rows.
- `report_initdoc_actionable_tail_digest_heartbeat_window.py` emits strict last-N summary.
- `scripts/graph_ui_server.py` includes `initdoc_actionable_tail.heartbeat_window`.
- `ui/graph/explorer-sources.html` card displays trend details.
- `.github/workflows/etl-tracker-gate.yml` extends `initdoc-actionable-tail-contract` with heartbeat/window fail-pass checks.
- `just` targets exist for report/check flows of heartbeat and window.

DoD:
- Unit tests + py_compile pass.
- Strict report checks pass on current DB (`actionable_missing=0`).
- Explorer snapshot and GH Pages build include trend block.
- Tracker/docs/sprint index updated with evidence links.
