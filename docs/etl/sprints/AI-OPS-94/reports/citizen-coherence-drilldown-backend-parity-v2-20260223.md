# Citizen Coherence Drilldown Backend Parity v2 (AI-OPS-94)

Date:
- 2026-02-23

Goal:
- Ensure `/citizen` coherence audit links and `/explorer-temas` coherence APIs share one consistent contract for party-scoped drilldown evidence.

What shipped:
- Backend coherence filter parity:
  - `scripts/graph_ui_server.py`
  - `/api/topics/coherence` now accepts `party_id`
  - `/api/topics/coherence/evidence` now accepts `party_id`
  - coherence evidence rows now include:
    - `party_id`
    - `party_name`
- Explorer URL-contract alignment:
  - `ui/graph/explorer-temas.html`
  - reads URL params from `/citizen` drilldown links:
    - `party_id`
    - `bucket`
    - `view=coherence`
    - `source=citizen_coherence`
  - forwards `party_id` to coherence API calls
  - auto-opens coherence evidence mode from URL intent
  - supports topic-only drilldown (without mandatory `topic_set_id`) for coherence/evidence load paths
- Tests:
  - `tests/test_graph_ui_server_coherence.py`
    - new party-filter coverage for coherence summary/evidence endpoints
  - `tests/test_explorer_temas_coherence_drilldown_url_contract.js`
    - URL-contract marker checks for explorer drilldown replay
- Lane wiring:
  - `justfile`
  - `just citizen-test-coherence-drilldown` now runs:
    - citizen drilldown contract test
    - explorer-temas URL contract test
    - backend coherence API unit tests

Validation:
- `just citizen-test-coherence-drilldown`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`
- `python3 -m unittest tests/test_graph_ui_server_coherence.py`
- `node --test tests/test_explorer_temas_coherence_drilldown_url_contract.js`

Strict parity-v2 result:
- `citizen-test-coherence-drilldown`: `pass=5 fail=0` (node) + `Ran 4 tests ... OK` (python)
- `coherence party filter endpoint tests`: PASS
- `explorer-temas URL contract tests`: PASS
- `citizen-release-regression-suite`: PASS (exit `0`)
- `explorer-gh-pages-build`: PASS

Evidence:
- `docs/etl/sprints/AI-OPS-94/evidence/just_citizen_test_coherence_drilldown_20260223T135524Z.txt`
- `docs/etl/sprints/AI-OPS-94/evidence/python_unittest_graph_ui_server_coherence_20260223T135524Z.txt`
- `docs/etl/sprints/AI-OPS-94/evidence/node_test_explorer_temas_coherence_drilldown_url_contract_20260223T135524Z.txt`
- `docs/etl/sprints/AI-OPS-94/evidence/explorer_temas_coherence_url_markers_20260223T135524Z.txt`
- `docs/etl/sprints/AI-OPS-94/evidence/just_citizen_release_regression_suite_20260223T135524Z.txt`
- `docs/etl/sprints/AI-OPS-94/evidence/just_explorer_gh_pages_build_20260223T135524Z.txt`
