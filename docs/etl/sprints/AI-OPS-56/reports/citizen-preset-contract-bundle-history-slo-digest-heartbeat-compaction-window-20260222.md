# Citizen Preset Contract Bundle History SLO Digest Heartbeat Compaction Window (AI-OPS-56)

Date:
- 2026-02-22

## What shipped

- New heartbeat compaction-window parity reporter:
  - `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window.js`
- Purpose:
  - compare raw vs compacted heartbeat streams over last-N
  - fail fast if latest or incident rows are missing after compaction

## Contract behavior

- Inputs:
  - raw heartbeat JSONL
  - compacted heartbeat JSONL
- Output:
  - JSON summary with:
    - `entries_total_raw`, `entries_total_compacted`, `window_raw_entries`
    - `raw_window_coverage_pct`, `incident_coverage_pct`
    - `missing_raw_ids_sample`, `missing_incident_ids_sample`
    - parity checks for latest/incident/failed/red
    - `strict_fail_reasons`
- Strict mode fails on:
  - empty raw window
  - malformed rows in raw window or compacted stream
  - latest raw row missing in compacted
  - incident rows missing in compacted
  - failed/red underreporting in compacted window parity

## Pipeline and CI integration

- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window`
- Workflow update:
  - `.github/workflows/etl-tracker-gate.yml` now generates strict compaction-window report and uploads:
    - `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window`
- Test suite update:
  - `just citizen-test-preset-codec` includes compaction-window parity tests.

## Evidence

- Compaction-window parity report:
  - `docs/etl/sprints/AI-OPS-56/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_report_20260222T223944Z.json`
  - Result: `window_raw_entries=4`, `missing_in_compacted_in_window=0`, `incident_missing_in_compacted=0`, `strict_fail_reasons=[]`
- Compaction report and compacted JSONL:
  - `docs/etl/sprints/AI-OPS-56/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_report_20260222T223944Z.json`
  - `docs/etl/sprints/AI-OPS-56/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compacted_20260222T223944Z.jsonl`
- Validation and gates:
  - `docs/etl/sprints/AI-OPS-56/evidence/citizen_preset_codec_tests_20260222T223944Z.txt` (`34/34`)
  - `docs/etl/sprints/AI-OPS-56/evidence/explorer_gh_pages_build_20260222T223944Z.txt`
  - `docs/etl/sprints/AI-OPS-56/evidence/tracker_gate_posttrackeredit_20260222T223944Z.txt`
- CI/just markers:
  - `docs/etl/sprints/AI-OPS-56/evidence/citizen_preset_ci_bundle_history_slo_digest_heartbeat_compaction_window_markers_20260222T223944Z.txt`

## Outcome

- Heartbeat compaction is now guarded by a strict parity layer that catches accidental loss of latest/incident rows before publication.
