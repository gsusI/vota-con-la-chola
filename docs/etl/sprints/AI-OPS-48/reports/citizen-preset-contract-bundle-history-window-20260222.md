# Citizen Preset Contract Bundle History Window (AI-OPS-48)

Date:
- 2026-02-22

Goal:
- Provide a strict summary of regressions over the latest N history entries for quick operational triage.

## What shipped

1. History-window reporter CLI
- Added `scripts/report_citizen_preset_contract_bundle_history_window.js`.
- Inputs:
  - `--history-jsonl`
  - `--last`
  - `--json-out`
  - `--strict`
- Output:
  - `window_last`
  - `entries_in_window`
  - `regressions_in_window`
  - `regression_events`
  - `latest_entry`

2. Test + local command integration
- Added `tests/test_report_citizen_preset_contract_bundle_history_window.js`:
  - strict pass on no-regression window
  - strict fail when window contains regression
- Added `just citizen-report-preset-contract-bundle-history-window`.
- Expanded `just citizen-test-preset-codec` to include history-window tests.

3. CI artifact
- Updated `.github/workflows/etl-tracker-gate.yml`:
  - runs strict history-window reporter in `citizen-preset-contract` job
  - uploads artifact `citizen-preset-contract-bundle-history-window`.

## Validation evidence

- Fixture contract report:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_report_20260222T213558Z.json`
- Codec parity report:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_codec_parity_report_20260222T213558Z.json`
- Codec sync-state report:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_codec_sync_report_20260222T213558Z.json`
- Bundle report:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_bundle_report_20260222T213558Z.json`
- Bundle-history report:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_bundle_history_report_20260222T213558Z.json`
- Bundle-history window report:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_bundle_history_window_report_20260222T213558Z.json`
- History tail snapshot:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_bundle_history_tail_20260222T213558Z.jsonl`
- Node tests:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_codec_tests_20260222T213558Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-48/evidence/explorer_gh_pages_build_20260222T213558Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-48/evidence/tracker_gate_posttrackeredit_20260222T213756Z.txt`
- CI markers:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_ci_bundle_history_window_markers_20260222T213558Z.txt`

Outcome:
- Operators can now inspect recent regressions in one strict report without manually diffing entire history logs.
