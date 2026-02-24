# AI-OPS-45 Prompt Pack

Objective:
- Make preset codec publish-sync state a strict, artifacted contract in local and CI flows.

Acceptance gates:
- New script: `scripts/report_citizen_preset_codec_sync_state.js`.
- Reporter supports `--source`, `--published`, `--json-out`, `--strict`.
- Reporter output includes `would_change`, before/after hashes, bytes delta, and first diff metadata.
- Node tests cover strict pass and strict fail for stale published asset.
- New `just` target: `citizen-report-preset-codec-sync`.
- CI uploads `citizen-preset-codec-sync` JSON artifact.
- Local controllable gates remain green.

Status update (2026-02-22):
- Added sync-state reporter and test coverage.
- Wired `just` and CI contract artifact for sync-state.
- evidence:
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_contract_report_20260222T212043Z.json`
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_codec_parity_report_20260222T212043Z.json`
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_codec_sync_report_20260222T212043Z.json`
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_codec_tests_20260222T212043Z.txt`
  - `docs/etl/sprints/AI-OPS-45/evidence/explorer_gh_pages_build_20260222T212043Z.txt`
  - `docs/etl/sprints/AI-OPS-45/evidence/tracker_gate_posttrackeredit_20260222T212350Z.txt`
  - `docs/etl/sprints/AI-OPS-45/evidence/citizen_preset_ci_sync_markers_20260222T212043Z.txt`
