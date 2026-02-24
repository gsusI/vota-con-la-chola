# AI-OPS-50 Prompt Pack

Objective:
- Add enforceable SLO thresholds on preset contract bundle history (rolling window) and publish machine-readable results in CI artifacts.

Acceptance gates:
- New script: `scripts/report_citizen_preset_contract_bundle_history_slo.js`.
- Inputs: `--history-jsonl`, `--last`, `--max-regressions`, `--max-regression-rate-pct`, `--min-green-streak`, `--json-out`, `--strict`.
- Output includes: `entries_in_window`, `regressions_in_window`, `regression_rate_pct`, `green_streak_latest`, `latest_entry_clean`, `checks`, `strict_fail_reasons`.
- Strict mode fails when any configured SLO check fails.
- New `just` target: `citizen-report-preset-contract-bundle-history-slo`.
- CI uploads artifact `citizen-preset-contract-bundle-history-slo`.

Status update (2026-02-22):
- Added SLO reporter, tests, `just` wiring, and CI artifact upload.
- Rolling window checks now surface threshold outcomes explicitly (`max_regressions`, `max_regression_rate_pct`, `min_green_streak`).
- Evidence chain remains green with tracker gate green.
- evidence:
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_codec_parity_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_codec_sync_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_window_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_compaction_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_slo_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_compacted_20260222T215303Z.jsonl`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_tail_20260222T215303Z.jsonl`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_codec_tests_20260222T215303Z.txt`
  - `docs/etl/sprints/AI-OPS-50/evidence/explorer_gh_pages_build_20260222T215303Z.txt`
  - `docs/etl/sprints/AI-OPS-50/evidence/tracker_gate_posttrackeredit_20260222T215303Z.txt`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_ci_bundle_history_slo_markers_20260222T215303Z.txt`
