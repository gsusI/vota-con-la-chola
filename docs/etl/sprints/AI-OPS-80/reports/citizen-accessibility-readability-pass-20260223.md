# Citizen Accessibility + Readability Pass (AI-OPS-80)

Date:
- 2026-02-23

Goal:
- Increase `/citizen` usability for keyboard-first and low-context users without adding backend complexity.

What shipped:
- Accessibility/readability pass in `ui/citizen/index.html`:
  - keyboard skip-link: `Saltar al contenido principal` -> `#citizenMain`
  - focus target: `<main id="citizenMain" tabindex="-1">`
  - live regions:
    - `#statusChips` (`role="status" aria-live="polite"`)
    - `#banner` (`role="status" aria-live="polite"`)
  - section semantics:
    - `aria-labelledby` for concern/items/compare sections
    - search/input aria labels (`Buscar preocupaciones`, `Buscar items por titulo`)
    - compare results region (`role="region" aria-label="Resultados por partido"`)
  - keyboard focus visibility improvements:
    - `.row:focus-visible`
    - `.smallLink:focus-visible`
    - `.skipLink:focus`
    - focused input/select ring
  - readability tuning:
    - base `line-height` increased to `1.45`
    - `.sub` line width tightened (`max-width: 76ch`)
    - hint/footer copy spacing improved.
- New strict contract test:
  - `tests/test_citizen_accessibility_readability_ui_contract.js`
- New `just` lane:
  - `just citizen-test-accessibility-readability`

Validation:
- `node --test tests/test_citizen_accessibility_readability_ui_contract.js`
- `just citizen-test-accessibility-readability`
- regression:
  - `just citizen-test-evidence-trust-panel`
  - `just citizen-test-mobile-performance`
  - `just citizen-test-first-answer-accelerator`
  - `just citizen-test-unknown-explainability`
  - `just citizen-test-concern-pack-quality`
- syntax:
  - `node --check` on extracted inline script from `ui/citizen/index.html`

Evidence:
- `docs/etl/sprints/AI-OPS-80/evidence/citizen_accessibility_readability_contract_summary_20260223T123520Z.json`
- `docs/etl/sprints/AI-OPS-80/evidence/citizen_accessibility_readability_contract_markers_20260223T123520Z.txt`
- `docs/etl/sprints/AI-OPS-80/evidence/just_citizen_test_accessibility_readability_20260223T123520Z.txt`
- `docs/etl/sprints/AI-OPS-80/evidence/node_test_citizen_accessibility_readability_ui_contract_20260223T123520Z.txt`
