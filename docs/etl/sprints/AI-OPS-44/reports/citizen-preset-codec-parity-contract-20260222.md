# Citizen Preset Codec Parity Contract (AI-OPS-44)

Date:
- 2026-02-22

Goal:
- Detect and fail fast when `ui/citizen/preset_codec.js` drifts from the published static copy `docs/gh-pages/citizen/preset_codec.js`.

## What shipped

1. New parity reporter CLI
- Added `scripts/report_citizen_preset_codec_parity.js`.
- Inputs:
  - `--source`
  - `--published`
  - `--json-out`
  - `--strict`
- Output:
  - `total_fail` + `failed_ids`
  - `source_sha256` / `published_sha256`
  - `source_bytes` / `published_bytes`
  - `first_diff_line` and differing line contents (when mismatch)

2. Test + local command integration
- Added `tests/test_report_citizen_preset_codec_parity.js`:
  - strict pass on identical files
  - strict fail on mismatch with asserted first-diff metadata
- Added `just citizen-report-preset-codec-parity`.
- Expanded `just citizen-test-preset-codec` to include the parity reporter tests.

3. CI artifact parity visibility
- Updated `.github/workflows/etl-tracker-gate.yml`:
  - `citizen-preset-contract` job now runs parity reporter strict mode.
  - New uploaded artifact: `citizen-preset-codec-parity` (`citizen_preset_codec_parity_ci.json`).
  - Artifact upload steps run with `if: always()` for triage visibility.

## Validation evidence

- Fixture contract report (strict pass):
  - `docs/etl/sprints/AI-OPS-44/evidence/citizen_preset_contract_report_20260222T211445Z.json`
- Codec parity report (strict pass):
  - `docs/etl/sprints/AI-OPS-44/evidence/citizen_preset_codec_parity_report_20260222T211445Z.json`
- Node tests:
  - `docs/etl/sprints/AI-OPS-44/evidence/citizen_preset_codec_tests_20260222T211445Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-44/evidence/explorer_gh_pages_build_20260222T211445Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-44/evidence/tracker_gate_postdocs_20260222T211445Z.txt`
- CI/just markers:
  - `docs/etl/sprints/AI-OPS-44/evidence/citizen_preset_ci_parity_markers_20260222T211445Z.txt`

Outcome:
- Source/published preset codec drift is now a first-class strict contract with machine-readable parity evidence across local and CI workflows.
