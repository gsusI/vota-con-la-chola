# AI-OPS-74 Report: Citizen First-Answer Accelerator

Date:
- 2026-02-23

Objective:
- Provide a deterministic recommendation path to get users to a first answer quickly, with direct evidence links.

What shipped:
- New shared module:
  - `ui/citizen/first_answer_accelerator.js`
  - output contract includes ranked concerns, recommended concern/topic, score, links, and `fallback_used`.
- UI integration:
  - `ui/citizen/index.html` loads module and computes `state.firstAnswerPlan`.
  - onboarding includes `Respuesta rapida recomendada` CTA (`data-first-answer-run`).
  - no-concern empty state includes inline accelerator CTA (`data-first-answer-run-inline`).
  - recommendation surfaces include explicit `Evidencia` / `Tema` links when available.
- Build/server wiring:
  - local route in `scripts/graph_ui_server.py`: `/citizen/first_answer_accelerator.js`
  - GH pages copy in `justfile`: `docs/gh-pages/citizen/first_answer_accelerator.js`
- Tests:
  - `tests/test_citizen_first_answer_accelerator.js`
  - `tests/test_citizen_first_answer_ui_contract.js`
  - target: `just citizen-test-first-answer-accelerator`

Validation evidence:
- `docs/etl/sprints/AI-OPS-74/evidence/node_test_first_answer_accelerator_20260223T104345Z.txt`
- `docs/etl/sprints/AI-OPS-74/evidence/node_check_first_answer_accelerator_20260223T104345Z.txt`
- `docs/etl/sprints/AI-OPS-74/evidence/node_check_citizen_inline_script_20260223T104345Z.txt`
- `docs/etl/sprints/AI-OPS-74/evidence/py_compile_graph_ui_server_20260223T104345Z.txt`
- `docs/etl/sprints/AI-OPS-74/evidence/python_unittest_graph_ui_server_citizen_assets_20260223T104345Z.txt`
- `docs/etl/sprints/AI-OPS-74/evidence/first_answer_contract_markers_20260223T104345Z.txt`
- `docs/etl/sprints/AI-OPS-74/evidence/first_answer_contract_summary_20260223T104345Z.json`
- regression guard:
  - `docs/etl/sprints/AI-OPS-74/evidence/node_test_onboarding_contract_regression_20260223T104345Z.txt`
