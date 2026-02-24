# Citizen Preset Codec Sync-State Contract (AI-OPS-45)

Date:
- 2026-02-22

Goal:
- Provide an explicit strict contract that answers: “Would publishing update `docs/gh-pages/citizen/preset_codec.js` right now?”

## What shipped

1. New sync-state reporter CLI
- Added `scripts/report_citizen_preset_codec_sync_state.js`.
- Inputs:
  - `--source`
  - `--published`
  - `--json-out`
  - `--strict`
- Output:
  - `would_change`
  - `published_before_sha256` and `published_after_sha256`
  - byte counts and `bytes_delta_after_sync`
  - first-diff metadata (`first_diff_line`, source/published line values)
  - `recommended_command` when stale

2. Test + local command integration
- Added `tests/test_report_citizen_preset_codec_sync_state.js`:
  - strict pass when already synchronized
  - strict fail when published copy is stale
- Expanded `just citizen-test-preset-codec` to include sync-state tests.
- Added `just citizen-report-preset-codec-sync`.

3. CI artifacted sync-state
- Updated `.github/workflows/etl-tracker-gate.yml`:
  - `citizen-preset-contract` job now runs sync-state report in strict mode.
  - New uploaded artifact: `citizen-preset-codec-sync` (`citizen_preset_codec_sync_ci.json`).

## Validation evidence

- Fixture contract report (strict pass):
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_contract_report_20260222T212043Z.json`
- Codec parity report (strict pass):
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_codec_parity_report_20260222T212043Z.json`
- Codec sync-state report (strict pass):
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_codec_sync_report_20260222T212043Z.json`
- Node tests:
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_codec_tests_20260222T212043Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-45/evidence/explorer_gh_pages_build_20260222T212043Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-45/evidence/tracker_gate_posttrackeredit_20260222T212350Z.txt`
- CI markers:
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_ci_sync_markers_20260222T212043Z.txt`

Outcome:
- The project now exposes both parity and publish-sync contracts for preset codec assets, each strict and artifacted for CI triage.
