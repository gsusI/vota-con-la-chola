# AI-OPS-79 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add an evidence trust panel to `/citizen` so users can see why a stance is shown and how trustworthy/fresh that evidence is.

Scope:
- `ui/citizen/evidence_trust_panel.js`
- `ui/citizen/index.html`
- `scripts/graph_ui_server.py`
- `scripts/report_citizen_mobile_performance_budget.py`
- `justfile`
- trust-panel contract/UI/server tests

Out-of-scope:
- ETL connector/source expansion
- changes to stance inference model
- server-side runtime dependencies for `/citizen`

Definition of done:
- Trust panel contract exists and is deterministic.
- `/citizen` renders trust chips/metadata with direct drill-down links.
- Local explorer + GH Pages include the new module asset.
- New tests pass and existing citizen regressions remain green.
- Sprint evidence + closeout are published in `docs/etl/sprints/AI-OPS-79/`.
