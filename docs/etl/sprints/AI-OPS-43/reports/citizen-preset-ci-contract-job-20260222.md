# Citizen Preset CI Contract Job (AI-OPS-43)

Date:
- 2026-02-22

Goal:
- Ensure citizen preset fixture drift is checked in CI and emitted as an artifact on every workflow run.

## What shipped

1. New CI job
- Added `citizen-preset-contract` to `.github/workflows/etl-tracker-gate.yml`.
- Steps:
  - checkout
  - setup node
  - run Node preset tests
  - run strict preset contract reporter
  - upload JSON report artifact

2. Artifact contract
- Artifact name: `citizen-preset-contract`
- Artifact payload: `citizen_preset_contract_ci.json`
- This makes failed/green contract reports inspectable per workflow run.

3. Compatibility
- Existing jobs (`tracker-gate`, `vote-smoke`, `hf-quality-contract`) remain unchanged in behavior.

## Validation evidence

- Workflow markers:
  - `docs/etl/sprints/AI-OPS-43/evidence/citizen_preset_ci_workflow_markers_20260222T211006Z.txt`
- Contract report (strict pass):
  - `docs/etl/sprints/AI-OPS-43/evidence/citizen_preset_contract_report_20260222T211006Z.json`
- Node tests:
  - `docs/etl/sprints/AI-OPS-43/evidence/citizen_preset_codec_tests_20260222T211006Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-43/evidence/explorer_gh_pages_build_20260222T211006Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-43/evidence/tracker_gate_posttrackeredit_20260222T211006Z.txt`

Outcome:
- Citizen preset contract drift is now enforced in CI with machine-readable artifact output.
