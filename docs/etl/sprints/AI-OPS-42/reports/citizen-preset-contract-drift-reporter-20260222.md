# Citizen Preset Contract Drift Reporter (AI-OPS-42)

Date:
- 2026-02-22

Goal:
- Add a one-command JSON reporter that quantifies preset fixture drift and pinpoints failing case IDs.

## What shipped

1. Reporter CLI
- Added `scripts/report_citizen_preset_fixture_contract.js`.
- Inputs:
  - `--fixture`
  - `--codec`
  - `--json-out`
  - `--strict`
- Output:
  - totals by section (`hash_cases_*`, `share_cases_*`)
  - `total_cases`, `total_fail`
  - `failed_ids`
  - per-case `results`

2. Strict drift mode
- In `--strict`, reporter exits `1` when any case fails.
- This enables fail-fast CI or local triage loops.

3. Test + command integration
- Added `tests/test_report_citizen_preset_fixture_contract.js`:
  - canonical fixture strict pass
  - forced drift strict fail with asserted `failed_ids`
- `just citizen-test-preset-codec` now runs codec + reporter tests.
- Added `just citizen-report-preset-contract` for direct JSON contract checks.

## Validation evidence

- Contract report (strict pass):
  - `docs/etl/sprints/AI-OPS-42/evidence/citizen_preset_contract_report_20260222T210553Z.json`
- Contract markers:
  - `docs/etl/sprints/AI-OPS-42/evidence/citizen_preset_contract_markers_20260222T210553Z.txt`
- Node tests:
  - `docs/etl/sprints/AI-OPS-42/evidence/citizen_preset_codec_tests_20260222T210553Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-42/evidence/explorer_gh_pages_build_20260222T210553Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-42/evidence/tracker_gate_posttrackeredit_20260222T210719Z.txt`

Outcome:
- Preset fixture drift can now be diagnosed quickly with stable IDs and machine-readable summary metrics.
