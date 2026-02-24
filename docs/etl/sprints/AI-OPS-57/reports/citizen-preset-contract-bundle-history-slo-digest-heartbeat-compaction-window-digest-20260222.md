# Citizen Preset Contract Bundle History SLO Digest Heartbeat Compaction Window Digest (AI-OPS-57)

Date:
- 2026-02-22

## What shipped

- New compact-window digest reporter:
  - `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest.js`
- Purpose:
  - convert full parity JSON into a compact alert-friendly payload
  - preserve strict-failure semantics while exposing softer degradation

## Contract behavior

- Input:
  - compaction-window parity JSON (`...heartbeat_compaction_window_report...json`)
- Output:
  - compact JSON with:
    - `status` (`ok/degraded/failed`)
    - `risk_level` (`green/amber/red`)
    - `risk_reasons` (soft alert hints)
    - `strict_fail_reasons` (hard guardrail breaks)
    - `key_metrics` + `key_checks` + thresholds
- Status semantics:
  - `failed`: any strict parity failure
  - `degraded`: strict pass but non-incident rows missing in compacted window
  - `ok`: full parity over window

## Pipeline and CI integration

- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest`
- Workflow update:
  - `.github/workflows/etl-tracker-gate.yml` now generates strict compact-window digest and uploads:
    - `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window-digest`
- Test suite update:
  - `just citizen-test-preset-codec` includes compact-window digest tests.

## Evidence

- Compact-window parity report:
  - `docs/etl/sprints/AI-OPS-57/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_report_20260222T224707Z.json`
  - Result: `window_raw_entries=1`, `missing_in_compacted_in_window=0`, `strict_fail_reasons=[]`
- Compact-window digest report:
  - `docs/etl/sprints/AI-OPS-57/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_report_20260222T224707Z.json`
  - Result: `status=ok`, `risk_level=green`, `validation_errors=[]`
- Validation and gates:
  - `docs/etl/sprints/AI-OPS-57/evidence/citizen_preset_codec_tests_20260222T224707Z.txt` (`37/37`)
  - `docs/etl/sprints/AI-OPS-57/evidence/explorer_gh_pages_build_20260222T224707Z.txt`
  - `docs/etl/sprints/AI-OPS-57/evidence/tracker_gate_posttrackeredit_20260222T224707Z.txt`
- CI/just markers:
  - `docs/etl/sprints/AI-OPS-57/evidence/citizen_preset_ci_bundle_history_slo_digest_heartbeat_compaction_window_digest_markers_20260222T224707Z.txt`

## Outcome

- Alert polling can now read one compact JSON status for heartbeat compaction-window health, without parsing full parity payloads.
