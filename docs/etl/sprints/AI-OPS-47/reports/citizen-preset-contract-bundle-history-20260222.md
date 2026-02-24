# Citizen Preset Contract Bundle History (AI-OPS-47)

Date:
- 2026-02-22

Goal:
- Persist contract-bundle run summaries and detect regressions against previous runs with strict machine-readable output.

## What shipped

1. Bundle-history reporter CLI
- Added `scripts/report_citizen_preset_contract_bundle_history.js`.
- Inputs:
  - `--bundle-json`
  - `--history-jsonl`
  - `--json-out`
  - `--strict`
- Output:
  - `history_size_before`, `history_size_after`
  - `regression_detected`, `regression_reasons`
  - `previous_entry` / `current_entry` summaries

2. Regression semantics
- Detects regression when compared to previous entry via:
  - increased `sections_fail`
  - increased `total_fail`
  - new failed sections
  - degraded contract flags
  - `sync_state.would_change` regressing from false to true

3. Test + command integration
- Added `tests/test_report_citizen_preset_contract_bundle_history.js`:
  - strict pass baseline append
  - strict fail on synthetic regression
- Added `just citizen-report-preset-contract-bundle-history`.
- Expanded `just citizen-test-preset-codec` to include history reporter tests.

4. CI artifact
- Updated `.github/workflows/etl-tracker-gate.yml`:
  - runs strict bundle-history report in `citizen-preset-contract` job
  - uploads artifact `citizen-preset-contract-bundle-history` (`.json` + `.jsonl`)

## Validation evidence

- Fixture contract report:
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_contract_report_20260222T213145Z.json`
- Codec parity report:
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_codec_parity_report_20260222T213145Z.json`
- Codec sync-state report:
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_codec_sync_report_20260222T213145Z.json`
- Bundle report:
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_contract_bundle_report_20260222T213145Z.json`
- Bundle-history report:
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_contract_bundle_history_report_20260222T213145Z.json`
- Bundle-history tail snapshot:
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_contract_bundle_history_tail_20260222T213145Z.jsonl`
- Node tests:
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_codec_tests_20260222T213145Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-47/evidence/explorer_gh_pages_build_20260222T213145Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-47/evidence/tracker_gate_posttrackeredit_20260222T213333Z.txt`
- CI markers:
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_ci_bundle_history_markers_20260222T213145Z.txt`

Outcome:
- Contract bundle trend tracking is now reproducible and strict, with history-backed regression detection and CI artifacts.
