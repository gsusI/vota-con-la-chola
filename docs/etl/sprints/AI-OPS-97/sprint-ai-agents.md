# AI-OPS-97 Prompt Pack

Objective:
- Ship explainability outcomes heartbeat v1 so `/citizen` keeps an append-only trend for explainability adoption with strict last-N window checks.

Acceptance gates:
- Add append-only heartbeat reporter for explainability outcomes digest (`scripts/report_citizen_explainability_outcomes_heartbeat.py`).
- Add strict window reporter for explainability outcomes heartbeat (`scripts/report_citizen_explainability_outcomes_heartbeat_window.py`).
- Ensure heartbeat captures contract-critical metrics (`glossary/help-copy interactions`, `adoption sessions`, `adoption completeness`, `contract_complete`).
- Add deterministic tests for heartbeat and window strict behavior.
- Wire `just` report/check/test lanes and include heartbeat tests in `citizen-release-regression-suite`.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`heartbeat_status=ok`, `window_status=ok`, `contract_complete=true`, `strict_fail_reasons=[]`).
