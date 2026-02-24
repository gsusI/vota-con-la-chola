# AI-OPS-92 Prompt Pack

Objective:
- Ship explainability outcomes digest v1 for `/citizen`: add glossary/help-copy interaction counters and enforce a strict adoption completeness gate.

Acceptance gates:
- Instrument explainability glossary/help-copy interactions in `ui/citizen/index.html` with local telemetry storage and debug export APIs.
- Add machine-readable reporter `scripts/report_citizen_explainability_outcomes.py` with `ok|degraded|failed` status, thresholds, and strict `contract_complete` behavior.
- Add deterministic fixture + tests for reporter and UI contract markers.
- Wire `just` report/check/test lanes and include the lane in `citizen-release-regression-suite`.
- Keep release regression suite and `explorer-gh-pages-build` green.
- Publish sprint evidence under `docs/etl/sprints/AI-OPS-92/evidence/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`status=ok`, `glossary_interactions=9`, `help_copy_interactions=5`, `adoption_completeness_rate=0.666667`).
