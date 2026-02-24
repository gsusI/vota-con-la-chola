# AI-OPS-49 Prompt Pack

Objective:
- Add long-run maintenance for preset contract history with deterministic compaction cadence and strict safety checks.

Acceptance gates:
- New script: `scripts/report_citizen_preset_contract_bundle_history_compaction.js`.
- Inputs: `--history-jsonl`, `--compacted-jsonl`, `--keep-recent`, `--keep-mid-span`, `--keep-mid-every`, `--keep-old-every`, `--min-raw-for-dropped-check`, `--json-out`, `--strict`.
- Output includes: `entries_total`, `selected_entries`, `dropped_entries`, `compaction_ratio_selected_pct`, `tiers`, `incidents_*`, `strict_fail_reasons`.
- Strict mode preserves safety (`latest_selected`, no dropped incidents, fail-safe checks).
- New `just` target: `citizen-report-preset-contract-bundle-history-compact`.
- CI uploads artifact `citizen-preset-contract-bundle-history-compaction`.

Status update (2026-02-22):
- Added compaction reporter, tests, `just` wiring, and CI artifact upload.
- History ledger remains append-only; compaction output is generated as a separate artifact.
- Strict chain remains green and tracker gate remains green.
- evidence:
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_codec_parity_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_codec_sync_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_window_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_compaction_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_compacted_20260222T214352Z.jsonl`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_tail_20260222T214352Z.jsonl`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_codec_tests_20260222T214352Z.txt`
  - `docs/etl/sprints/AI-OPS-49/evidence/explorer_gh_pages_build_20260222T214352Z.txt`
  - `docs/etl/sprints/AI-OPS-49/evidence/tracker_gate_posttrackeredit_20260222T214352Z.txt`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_ci_bundle_history_compaction_markers_20260222T214352Z.txt`
