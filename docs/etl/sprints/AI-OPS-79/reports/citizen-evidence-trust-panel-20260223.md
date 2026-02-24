# Citizen Evidence Trust Panel (AI-OPS-79)

Date:
- 2026-02-23

Goal:
- Make trust and freshness explicit in `/citizen` answers without adding backend complexity.

What shipped:
- New deterministic trust-panel module:
  - `ui/citizen/evidence_trust_panel.js`
  - exposes `buildEvidenceTrustPanel(input)` with:
    - `panel_version=evidence_trust_panel_v1`
    - method labels (`combined|votes|declared`)
    - source-age freshness tiers (`fresh|aging|stale|unknown`)
    - trust levels (`high|medium|low`) and machine-readable reasons
    - drill-down link availability (`explorer_temas|explorer_positions|explorer_evidence`)
- `/citizen` UI integration (`ui/citizen/index.html`):
  - loads `./evidence_trust_panel.js`
  - renders trust markers in party cards:
    - `data-evidence-trust-panel`
    - `data-evidence-trust-freshness`
    - visible tags: `fuente_<tier>`, `edad_fuente=<days>`, `metodo=<label>`
  - computes per-party topic coverage helper (`trustCoverageForPartyTopics`) to feed the trust panel.
- Build/runtime wiring:
  - `justfile` adds `citizen-test-evidence-trust-panel` and GH copy for `evidence_trust_panel.js`
  - `scripts/report_citizen_mobile_performance_budget.py` includes the new asset in budget checks
  - `scripts/graph_ui_server.py` serves `/citizen/evidence_trust_panel.js` and includes `/citizen/data/concern_pack_quality.json` route parity.
- New tests:
  - `tests/test_citizen_evidence_trust_panel.js`
  - `tests/test_citizen_evidence_trust_panel_ui_contract.js`
  - `tests/test_graph_ui_server_citizen_assets.py`

Validation:
- `node --test tests/test_citizen_evidence_trust_panel.js tests/test_citizen_evidence_trust_panel_ui_contract.js`
- `just citizen-test-evidence-trust-panel`
- `python3 -m unittest tests/test_graph_ui_server_citizen_assets.py`
- syntax/compile:
  - `node --check ui/citizen/evidence_trust_panel.js`
  - inline script syntax extraction check for `ui/citizen/index.html`
  - `python3 -m py_compile scripts/graph_ui_server.py scripts/report_citizen_mobile_performance_budget.py`
- regression:
  - `just citizen-test-preset-codec`
  - `just citizen-test-mobile-performance`
  - `just citizen-test-first-answer-accelerator`
  - `just citizen-test-unknown-explainability`
  - `just citizen-test-concern-pack-quality`

Evidence:
- `docs/etl/sprints/AI-OPS-79/evidence/citizen_evidence_trust_panel_contract_summary_20260223T112805Z.json`
- `docs/etl/sprints/AI-OPS-79/evidence/citizen_evidence_trust_panel_contract_markers_20260223T112805Z.txt`
- `docs/etl/sprints/AI-OPS-79/evidence/just_citizen_test_evidence_trust_panel_20260223T112805Z.txt`
- `docs/etl/sprints/AI-OPS-79/evidence/node_test_citizen_evidence_trust_panel_20260223T112805Z.txt`
- `docs/etl/sprints/AI-OPS-79/evidence/python_unittest_graph_ui_server_citizen_assets_20260223T112805Z.txt`
