# AI-OPS-73 Report: Citizen Onboarding Funnel Hardening

Date:
- 2026-02-23

Objective:
- Harden onboarding with a deterministic step contract and a direct "next best action" jump.

What shipped:
- New shared module:
  - `ui/citizen/onboarding_funnel.js`
  - outputs funnel checks, required completion %, and `next_action` (`apply_pack|select_concern|open_topic|open_alignment|set_preference|done`)
- UI integration:
  - `ui/citizen/index.html` now uses onboarding contract and renders a `data-onboard-next` CTA
  - CTA executes deterministic action order (pack -> concern -> topic -> alignment -> preference)
- Strict tests:
  - `tests/test_citizen_onboarding_funnel.js`
  - `tests/test_citizen_onboarding_ui_contract.js`
  - `just citizen-test-onboarding-funnel`
- Distribution wiring:
  - local server route: `scripts/graph_ui_server.py` serves `/citizen/onboarding_funnel.js`
  - GH Pages build copy: `justfile` copies `ui/citizen/onboarding_funnel.js` to `docs/gh-pages/citizen/onboarding_funnel.js`

Validation evidence:
- `docs/etl/sprints/AI-OPS-73/evidence/node_test_citizen_onboarding_contract_20260223T103616Z.txt`
- `docs/etl/sprints/AI-OPS-73/evidence/node_check_onboarding_funnel_20260223T103616Z.txt`
- `docs/etl/sprints/AI-OPS-73/evidence/node_check_citizen_inline_script_20260223T103616Z.txt`
- `docs/etl/sprints/AI-OPS-73/evidence/py_compile_graph_ui_server_20260223T103616Z.txt`
- `docs/etl/sprints/AI-OPS-73/evidence/onboarding_contract_markers_20260223T103616Z.txt`
- `docs/etl/sprints/AI-OPS-73/evidence/onboarding_contract_summary_20260223T103616Z.json`
