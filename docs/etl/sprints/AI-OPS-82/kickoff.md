# AI-OPS-82 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add explicit cross-method stability diagnostics to coherence mode so users can see where answers are stable vs uncertain across `votes`, `declared`, and `combined`.

Scope:
- `ui/citizen/cross_method_stability.js`
- `ui/citizen/index.html` (coherence panel integration)
- `justfile` cross-method test lane + regression suite update
- `scripts/report_citizen_mobile_performance_budget.py`
- `scripts/graph_ui_server.py`
- strict tests and sprint evidence

Out-of-scope:
- changes to ETL inference logic
- schema migrations
- backend API additions

Definition of done:
- Stability module computes pairwise metrics and uncertainty reasons deterministically.
- Coherence view renders stability markers (`status`, `uncertainty`) from module output.
- Build/server/perf/release-hardening contracts include the new asset.
- New tests pass and existing citizen regressions stay green.
- Sprint evidence + closeout are published in `docs/etl/sprints/AI-OPS-82/`.
