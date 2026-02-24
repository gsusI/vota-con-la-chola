# Citizen Unknown Explainability v2 (AI-OPS-75)

Date:
- 2026-02-23

Goal:
- Make `unknown` actionable for citizens by answering two questions directly in the UI:
  - why is this unknown?
  - what would reduce uncertainty?

What shipped:
- New shared module `ui/citizen/unknown_explainability.js` (UMD):
  - deterministic dominant-cause detection (`no_signal`, `unclear`, `mixed`, `none`)
  - reason labels/details and "reduce uncertainty" guidance
  - stable numeric summary fields (`unknown_total`, `unknown_ratio`, coverage)
- UI integration in `ui/citizen/index.html`:
  - loads `./unknown_explainability.js`
  - adds helper wrappers `buildUnknownExplainability`, `renderUnknownExplainabilityHint`
  - renders summary-level hints (`data-unknown-explainability-summary`) for:
    - dashboard multi-concern aggregate
    - concern aggregate
    - selected topic aggregate
  - renders card-level hints (`data-unknown-explainability`) for:
    - dashboard party cards
    - concern party cards
    - topic party cards
- Build/server wiring:
  - `scripts/graph_ui_server.py` serves `/citizen/unknown_explainability.js`
  - `justfile` copies module into GH pages output and adds `citizen-test-unknown-explainability`

Validation:
- `just citizen-test-unknown-explainability`
- `just citizen-test-first-answer-accelerator`
- `python3 -m unittest tests/test_graph_ui_server_citizen_assets.py`
- `node --check ui/citizen/unknown_explainability.js`
- `node --check` on extracted inline script from `ui/citizen/index.html`
- `python3 -m py_compile scripts/graph_ui_server.py`

Evidence:
- `docs/etl/sprints/AI-OPS-75/evidence/unknown_explainability_contract_summary_20260223T105432Z.json`
- `docs/etl/sprints/AI-OPS-75/evidence/unknown_explainability_contract_markers_20260223T105432Z.txt`
- `docs/etl/sprints/AI-OPS-75/evidence/node_test_unknown_explainability_20260223T105432Z.txt`
- `docs/etl/sprints/AI-OPS-75/evidence/node_test_first_answer_regression_20260223T105432Z.txt`
