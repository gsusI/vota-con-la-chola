# Citizen Preset Contract Bundle (AI-OPS-46)

Date:
- 2026-02-22

Goal:
- Produce a single strict JSON artifact that combines fixture contract, codec parity, and codec sync-state for one-shot triage.

## What shipped

1. Bundle reporter CLI
- Added `scripts/report_citizen_preset_contract_bundle.js`.
- Inputs:
  - `--fixture`
  - `--source`
  - `--published`
  - `--json-out`
  - `--strict`
- Output:
  - global summary (`sections_total/pass/fail`, `failed_sections`, `failed_ids`)
  - per-contract status blocks (`ok/status/signal/error/summary`)
  - nested full subreports for `fixture_contract`, `codec_parity`, `codec_sync_state`.

2. Test + local command integration
- Added `tests/test_report_citizen_preset_contract_bundle.js`:
  - strict pass when all subcontracts pass
  - strict fail when published asset is stale
- Added `just citizen-report-preset-contract-bundle`.
- Expanded `just citizen-test-preset-codec` to include bundle tests.

3. CI bundle artifact
- Updated `.github/workflows/etl-tracker-gate.yml`:
  - `citizen-preset-contract` job now runs bundle reporter in strict mode.
  - New artifact upload: `citizen-preset-contract-bundle` (`citizen_preset_contract_bundle_ci.json`).

## Validation evidence

- Fixture contract report (strict pass):
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_contract_report_20260222T212633Z.json`
- Codec parity report (strict pass):
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_codec_parity_report_20260222T212633Z.json`
- Codec sync-state report (strict pass):
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_codec_sync_report_20260222T212633Z.json`
- Bundle report (strict pass):
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_contract_bundle_report_20260222T212633Z.json`
- Node tests:
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_codec_tests_20260222T212633Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-46/evidence/explorer_gh_pages_build_20260222T212633Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-46/evidence/tracker_gate_posttrackeredit_20260222T212821Z.txt`
- CI markers:
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_ci_bundle_markers_20260222T212633Z.txt`

Outcome:
- Preset contract triage now has a canonical single-file artifact suitable for CI debugging, handoffs, and historical run comparison.
