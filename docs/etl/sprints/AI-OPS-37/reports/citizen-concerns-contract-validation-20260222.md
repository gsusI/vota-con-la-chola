# Citizen Concerns Contract Validation (AI-OPS-37)

Date:
- 2026-02-22

Goal:
- Prevent silent regressions in citizen concern/packs config by validating the config contract during the canonical static build.

## What shipped

1. New validator for `concerns_v1`
- Added `scripts/validate_citizen_concerns.py`.
- Contract checks include:
  - required root keys: `version`, `concerns`, `packs`
  - concern keys/types: `id`, `label`, `description`, `keywords`
  - pack keys/types: `id`, `label`, `concern_ids`, `tradeoff`
  - pack references only known concern ids
  - every concern must be represented in at least one pack

2. Unit test coverage
- Added `tests/test_validate_citizen_concerns.py` with:
  - valid minimal config test
  - failure-mode test for duplicate concern id, unknown pack reference, and missing required fields
  - real repo config test (`ui/citizen/concerns_v1.json`)

3. Build integration
- `just explorer-gh-pages-build` now runs concerns validation right after copying citizen assets to GH Pages output.
- Result: malformed config now fails fast in the reproducible build path.

## Validation Evidence

- Validator report:
  - `docs/etl/sprints/AI-OPS-37/evidence/citizen_concerns_validate_20260222T202800Z.json`
- Validator marker scan:
  - `docs/etl/sprints/AI-OPS-37/evidence/citizen_concerns_validator_markers_20260222T202754Z.txt`
- Unit tests:
  - `docs/etl/sprints/AI-OPS-37/evidence/validate_citizen_concerns_tests_20260222T202804Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-37/evidence/explorer_gh_pages_build_20260222T202659Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-37/evidence/tracker_gate_20260222T202727Z.txt`

Outcome:
- Citizen config now has an explicit, test-backed contract enforced in build, reducing UI drift risk while preserving static-first delivery.
