# AI-OPS-47 Prompt Pack

Objective:
- Add persistent bundle-history tracking with strict regression signaling for citizen preset contracts.

Acceptance gates:
- New script: `scripts/report_citizen_preset_contract_bundle_history.js`.
- Inputs: `--bundle-json`, `--history-jsonl`, `--json-out`, `--strict`.
- Output includes: `history_size_before`, `history_size_after`, `regression_detected`, `regression_reasons`, previous/current entry summaries.
- Strict mode fails on regressions.
- New `just` target: `citizen-report-preset-contract-bundle-history`.
- CI uploads artifact `citizen-preset-contract-bundle-history`.
- Existing strict reports stay green.

Status update (2026-02-22):
- Added bundle-history reporter, tests, just target, and CI artifact upload.
- Started history ledger at `docs/etl/runs/citizen_preset_contract_bundle_history.jsonl`.
- evidence:
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_contract_report_20260222T213145Z.json`
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_codec_parity_report_20260222T213145Z.json`
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_codec_sync_report_20260222T213145Z.json`
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_contract_bundle_report_20260222T213145Z.json`
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_contract_bundle_history_report_20260222T213145Z.json`
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_contract_bundle_history_tail_20260222T213145Z.jsonl`
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_codec_tests_20260222T213145Z.txt`
  - `docs/etl/sprints/AI-OPS-47/evidence/explorer_gh_pages_build_20260222T213145Z.txt`
  - `docs/etl/sprints/AI-OPS-47/evidence/tracker_gate_posttrackeredit_20260222T213333Z.txt`
  - `docs/etl/sprints/AI-OPS-47/evidence/citizen_preset_ci_bundle_history_markers_20260222T213145Z.txt`
