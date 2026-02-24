# AI-OPS-48 Prompt Pack

Objective:
- Add regression-window visibility for preset contract history (`last N`) with strict machine-readable output.

Acceptance gates:
- New script: `scripts/report_citizen_preset_contract_bundle_history_window.js`.
- Inputs: `--history-jsonl`, `--last`, `--json-out`, `--strict`.
- Output includes: `entries_in_window`, `regressions_in_window`, `regression_events`, `latest_entry`.
- Strict mode fails when regressions are present in window.
- New `just` target: `citizen-report-preset-contract-bundle-history-window`.
- CI uploads artifact `citizen-preset-contract-bundle-history-window`.

Status update (2026-02-22):
- Added history-window reporter, tests, just target, and CI artifact upload.
- History ledger now has 2 entries with zero regressions in the last-20 window.
- evidence:
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_report_20260222T213558Z.json`
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_codec_parity_report_20260222T213558Z.json`
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_codec_sync_report_20260222T213558Z.json`
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_bundle_report_20260222T213558Z.json`
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_bundle_history_report_20260222T213558Z.json`
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_bundle_history_window_report_20260222T213558Z.json`
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_contract_bundle_history_tail_20260222T213558Z.jsonl`
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_codec_tests_20260222T213558Z.txt`
  - `docs/etl/sprints/AI-OPS-48/evidence/explorer_gh_pages_build_20260222T213558Z.txt`
  - `docs/etl/sprints/AI-OPS-48/evidence/tracker_gate_posttrackeredit_20260222T213756Z.txt`
  - `docs/etl/sprints/AI-OPS-48/evidence/citizen_preset_ci_bundle_history_window_markers_20260222T213558Z.txt`
