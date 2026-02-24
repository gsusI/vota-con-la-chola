# Citizen Cross-Method Stability Panel (AI-OPS-82)

Date:
- 2026-02-23

Goal:
- Make answer stability explicit across `votes`, `declared`, and `combined` in coherence mode, including uncertainty causes.

What shipped:
- New deterministic module:
  - `ui/citizen/cross_method_stability.js`
  - exposes `buildCrossMethodStability(input)` with:
    - pair metrics: `votes_declared`, `combined_votes`, `combined_declared`
    - comparable coverage and mismatch rates
    - weighted stability score
    - `status` (`stable|mixed|unstable|uncertain|unknown`)
    - uncertainty attribution (`uncertainty_level`, `uncertainty_reasons`, `reason_label`, `reason_detail`)
- `/citizen` coherence integration (`ui/citizen/index.html`):
  - loads `./cross_method_stability.js`
  - computes cross-method rows from current concern/topic scope
  - renders summary panel with markers:
    - `data-cross-method-stability`
    - `data-cross-method-status`
    - `data-cross-method-uncertainty`
- Build/runtime wiring:
  - `justfile`: new `citizen-test-cross-method-stability`, regression suite includes cross-method lane
  - `justfile`: GH Pages build copies `ui/citizen/cross_method_stability.js`
  - `scripts/report_citizen_mobile_performance_budget.py`: includes new asset in budget list
  - `scripts/graph_ui_server.py`: serves `/citizen/cross_method_stability.js`
  - `tests/test_graph_ui_server_citizen_assets.py`: verifies route/constant
- Release hardening alignment:
  - `scripts/report_citizen_release_hardening.js`, `justfile`, and `tests/test_report_citizen_release_hardening.js` now include `cross_method_stability.js` in parity checks.

Validation:
- `node --test tests/test_citizen_cross_method_stability.js tests/test_citizen_cross_method_stability_ui_contract.js`
- `just citizen-test-cross-method-stability`
- `python3 -m unittest tests/test_graph_ui_server_citizen_assets.py`
- regressions:
  - `just citizen-test-mobile-performance`
  - `just citizen-test-evidence-trust-panel`
  - `just citizen-test-accessibility-readability`
  - `just citizen-test-first-answer-accelerator`
  - `just citizen-test-unknown-explainability`
  - `just citizen-test-concern-pack-quality`
  - `just citizen-test-release-hardening`
- release-ready path:
  - `just explorer-gh-pages-build`
  - `just citizen-check-release-hardening`

Evidence:
- `docs/etl/sprints/AI-OPS-82/evidence/citizen_cross_method_stability_contract_summary_20260223T135145Z.json`
- `docs/etl/sprints/AI-OPS-82/evidence/citizen_cross_method_stability_contract_markers_20260223T135145Z.txt`
- `docs/etl/sprints/AI-OPS-82/evidence/just_citizen_test_cross_method_stability_20260223T133738Z.txt`
- `docs/etl/sprints/AI-OPS-82/evidence/just_citizen_check_release_hardening_20260223T135145Z.txt`
