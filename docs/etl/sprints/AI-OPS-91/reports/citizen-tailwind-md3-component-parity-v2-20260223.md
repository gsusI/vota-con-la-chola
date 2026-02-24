# Citizen Tailwind+MD3 Component Parity v2 (AI-OPS-91)

Date:
- 2026-02-23

Goal:
- Normalize MD3 primitives across `/citizen` UI surfaces so static and dynamic components share one consistent style contract.

What shipped:
- MD3 primitive expansion in generated CSS:
  - `scripts/build_citizen_tailwind_md3_css.py`
  - added/updated primitives:
    - `md3-button` (tonal baseline)
    - `md3-button-primary`
    - `md3-tab`
- `/citizen` class normalization:
  - `ui/citizen/index.html`
  - static controls now use `md3-tab` (view/method/stance/sort/topic limit)
  - button/chip/tag/card templates now emit MD3 classes:
    - `btn md3-button`
    - `chip md3-chip`
    - `tag tagbtn md3-tab`
    - `partyCard md3-card`
- Contract hardening:
  - `scripts/report_citizen_tailwind_md3_contract.py`
  - adds strict marker-count checks:
    - `min_md3_card_markers`
    - `min_md3_chip_markers`
    - `min_md3_button_markers`
    - `min_md3_tab_markers`
- Just lane wiring:
  - `justfile`
  - adds default marker thresholds for strict check lane:
    - cards `>=6`
    - chips `>=8`
    - buttons `>=20`
    - tabs `>=6`
- Test updates:
  - `tests/test_citizen_tailwind_md3_ui_contract.js`
  - `tests/test_build_citizen_tailwind_md3_css.py`
  - `tests/test_report_citizen_tailwind_md3_contract.py`

Validation:
- `just citizen-test-tailwind-md3`
- `just citizen-check-tailwind-md3-sync`
- `just citizen-report-tailwind-md3`
- `just citizen-check-tailwind-md3`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict parity-v2 result:
- `status=ok`
- `generated_css_bytes=6533`
- `md3_card_markers=10` (threshold `6`)
- `md3_chip_markers=16` (threshold `8`)
- `md3_button_markers=28` (threshold `20`)
- `md3_tab_markers=9` (threshold `6`)

Evidence:
- `docs/etl/sprints/AI-OPS-91/evidence/citizen_tailwind_md3_contract_latest.json`
- `docs/etl/sprints/AI-OPS-91/evidence/citizen_tailwind_md3_contract_20260223T132224Z.json`
- `docs/etl/sprints/AI-OPS-91/evidence/citizen_tailwind_md3_contract_summary_20260223T132224Z.json`
- `docs/etl/sprints/AI-OPS-91/evidence/citizen_tailwind_md3_parity_markers_20260223T132224Z.txt`
- `docs/etl/sprints/AI-OPS-91/evidence/just_citizen_test_tailwind_md3_20260223T132224Z.txt`
- `docs/etl/sprints/AI-OPS-91/evidence/just_citizen_check_tailwind_md3_20260223T132224Z.txt`
- `docs/etl/sprints/AI-OPS-91/evidence/just_citizen_release_regression_suite_20260223T132224Z.txt`
- `docs/etl/sprints/AI-OPS-91/evidence/just_explorer_gh_pages_build_20260223T132224Z.txt`
