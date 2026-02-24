# Citizen Preset Contract Bundle History SLO (AI-OPS-50)

Date:
- 2026-02-22

## What shipped

- Added `scripts/report_citizen_preset_contract_bundle_history_slo.js`.
- Added rolling-window SLO checks over bundle-history:
  - `max_regressions`
  - `max_regression_rate_pct`
  - `min_green_streak`
  - implicit `latest_entry_clean`
- Added strict mode that fails fast with explicit `strict_fail_reasons`.

## Test coverage

- Added `tests/test_report_citizen_preset_contract_bundle_history_slo.js`:
  - strict pass on clean window with zero regressions
  - strict fail on regression + dirty latest entry
- Updated `just citizen-test-preset-codec` to include SLO tests.

## Tooling/CI integration

- Added `just citizen-report-preset-contract-bundle-history-slo` plus env vars:
  - `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_WINDOW`
  - `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_MAX_REGRESSIONS`
  - `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_MAX_REGRESSION_RATE_PCT`
  - `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_MIN_GREEN_STREAK`
  - `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_OUT`
- Updated `.github/workflows/etl-tracker-gate.yml`:
  - includes SLO test in Node test run
  - generates strict SLO report artifact
  - uploads artifact `citizen-preset-contract-bundle-history-slo`

## Evidence

- Strict reports:
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_codec_parity_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_codec_sync_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_window_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_compaction_report_20260222T215303Z.json`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_slo_report_20260222T215303Z.json`
- History snapshots:
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_tail_20260222T215303Z.jsonl`
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_contract_bundle_history_compacted_20260222T215303Z.jsonl`
- Validation/build/gate:
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_codec_tests_20260222T215303Z.txt` (`20/20`)
  - `docs/etl/sprints/AI-OPS-50/evidence/explorer_gh_pages_build_20260222T215303Z.txt`
  - `docs/etl/sprints/AI-OPS-50/evidence/tracker_gate_posttrackeredit_20260222T215303Z.txt`
- CI marker references:
  - `docs/etl/sprints/AI-OPS-50/evidence/citizen_preset_ci_bundle_history_slo_markers_20260222T215303Z.txt`

## Outcome

- Preset history observability now includes explicit threshold-based SLO enforcement, not only binary regression detection, improving long-run operational guardrails.
