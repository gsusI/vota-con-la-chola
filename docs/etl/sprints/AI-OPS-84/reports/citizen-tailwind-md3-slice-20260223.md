# Citizen Tailwind + MD3 Slice (AI-OPS-84)

Date:
- 2026-02-23

Goal:
- Deliver a deterministic Tailwind+MD3 design-system layer for `/citizen` that is build-time generated, contract-tested, and release-hardened.

What shipped:
- New token source of truth:
  - `ui/citizen/tailwind_md3.tokens.json`
- New deterministic builder:
  - `scripts/build_citizen_tailwind_md3_css.py`
  - generates `ui/citizen/tailwind_md3.generated.css`
  - supports `--check` drift mode for sync gating
- `/citizen` integration:
  - `ui/citizen/index.html` now loads `./tailwind_md3.generated.css`
  - adds MD3 primitive class markers in static shell (`md3-card`, `md3-chip`)
- New strict contract reporter:
  - `scripts/report_citizen_tailwind_md3_contract.py`
  - checks token shape/schema, generated CSS budget+markers, and UI integration markers
- Build/runtime wiring:
  - `just explorer-gh-pages-build` now rebuilds CSS and publishes:
    - `docs/gh-pages/citizen/tailwind_md3.generated.css`
    - `docs/gh-pages/citizen/tailwind_md3.tokens.json`
    - `docs/gh-pages/citizen/data/tailwind_md3.tokens.json`
  - `scripts/graph_ui_server.py` now serves:
    - `/citizen/tailwind_md3.generated.css`
    - `/citizen/tailwind_md3.tokens.json`
    - `/citizen/data/tailwind_md3.tokens.json`
- Release parity integration:
  - `scripts/report_citizen_release_hardening.js` default assets now include:
    - `tailwind_md3.generated.css`
    - `tailwind_md3.tokens.json`
- `just` lanes added:
  - `just citizen-build-tailwind-md3`
  - `just citizen-check-tailwind-md3-sync`
  - `just citizen-report-tailwind-md3`
  - `just citizen-check-tailwind-md3`
  - `just citizen-test-tailwind-md3`
  - included in `just citizen-release-regression-suite`

Validation:
- `just citizen-test-tailwind-md3`
- `just citizen-build-tailwind-md3`
- `just citizen-check-tailwind-md3-sync`
- `just citizen-report-tailwind-md3`
- `just citizen-check-tailwind-md3`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`
- `just citizen-check-release-hardening`

Strict Tailwind+MD3 contract result:
- `status=ok`
- `generated_css_bytes=5582`
- `token_colors_count=15`
- `token_spacing_count=6`
- threshold:
  - `max_generated_css_bytes=40000`

Evidence:
- `docs/etl/sprints/AI-OPS-84/evidence/citizen_tailwind_md3_contract_summary_20260223T121259Z.json`
- `docs/etl/sprints/AI-OPS-84/evidence/citizen_tailwind_md3_contract_markers_20260223T121259Z.txt`
- `docs/etl/sprints/AI-OPS-84/evidence/just_citizen_check_tailwind_md3_20260223T121235Z.txt`
- `docs/etl/sprints/AI-OPS-84/evidence/just_citizen_release_regression_suite_20260223T121235Z.txt`
- `docs/etl/sprints/AI-OPS-84/evidence/just_citizen_check_release_hardening_20260223T121235Z.txt`
