# Citizen Preset Contract Bundle History Compaction (AI-OPS-49)

Date:
- 2026-02-22

## What shipped

- Added `scripts/report_citizen_preset_contract_bundle_history_compaction.js`.
- Added deterministic cadence compaction over append-only history:
  - recent tier: keep every row (`keep_recent`)
  - mid tier: keep every N rows (`keep_mid_every` within `keep_mid_span`)
  - old tier: keep every N rows (`keep_old_every`)
- Added safety constraints in strict mode:
  - keep latest entry
  - keep incident entries
  - optional dropped-row expectation above `min_raw_for_dropped_check`
- Added optional compacted JSONL artifact output (`--compacted-jsonl`) without mutating canonical history.

## Test coverage

- Added `tests/test_report_citizen_preset_contract_bundle_history_compaction.js`:
  - strict pass path: compaction drops rows while preserving incident entry
  - strict fail path: fails when no rows are dropped above configured threshold
- Updated `just citizen-test-preset-codec` to include new test suite.

## Tooling/CI integration

- Added `just citizen-report-preset-contract-bundle-history-compact` plus env vars for cadence and output paths.
- Updated `.github/workflows/etl-tracker-gate.yml`:
  - includes history-window + compaction tests in Node test run
  - generates strict compaction report
  - uploads artifact `citizen-preset-contract-bundle-history-compaction`

## Evidence

- Strict reports:
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_codec_parity_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_codec_sync_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_window_report_20260222T214352Z.json`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_compaction_report_20260222T214352Z.json`
- History snapshots:
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_tail_20260222T214352Z.jsonl`
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_contract_bundle_history_compacted_20260222T214352Z.jsonl`
- Validation/build/gate:
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_codec_tests_20260222T214352Z.txt` (`18/18`)
  - `docs/etl/sprints/AI-OPS-49/evidence/explorer_gh_pages_build_20260222T214352Z.txt`
  - `docs/etl/sprints/AI-OPS-49/evidence/tracker_gate_posttrackeredit_20260222T214352Z.txt`
- CI marker references:
  - `docs/etl/sprints/AI-OPS-49/evidence/citizen_preset_ci_bundle_history_compaction_markers_20260222T214352Z.txt`

## Outcome

- Contract-history observability now has a deterministic maintenance lane for long-lived JSONL history while preserving regression/incident auditability.
