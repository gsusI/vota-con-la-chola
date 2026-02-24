# Citizen Preset Contract Bundle History SLO Digest Heartbeat Compaction (AI-OPS-55)

Date:
- 2026-02-22

## What shipped

- New heartbeat compaction reporter:
  - `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction.js`
- Purpose:
  - cap long-term heartbeat history growth with deterministic cadence
  - preserve alert-critical rows (`failed`, `red`, malformed, strict-fail rows)

## Contract behavior

- Input:
  - heartbeat JSONL (`report_citizen_preset_contract_bundle_history_slo_digest_heartbeat.js`)
- Output:
  - JSON summary with:
    - policy (`keep_recent`, `keep_mid_span`, `keep_mid_every`, `keep_old_every`)
    - size metrics (`entries_total`, `selected_entries`, `dropped_entries`, `selected_ratio`)
    - safety counters (`incidents_*`, `failed_*`, `red_*`, `malformed_*`)
    - tier summaries and reason samples
    - `strict_fail_reasons`
- Strict mode fails on:
  - empty history/selection
  - latest row not selected
  - incident rows dropped
  - no dropped rows when above configured raw-size threshold

## Pipeline and CI integration

- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact`
- Workflow update:
  - `.github/workflows/etl-tracker-gate.yml` now generates strict heartbeat-compaction report and uploads:
    - `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction`
- Test suite update:
  - `just citizen-test-preset-codec` includes heartbeat-compaction tests.

## Evidence

- Heartbeat-compaction report:
  - `docs/etl/sprints/AI-OPS-55/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_report_20260222T223021Z.json`
  - Result: `entries_total=3`, `selected_entries=3`, `incidents_dropped=0`, `strict_fail_reasons=[]`
- Compacted heartbeat JSONL:
  - `docs/etl/sprints/AI-OPS-55/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compacted_20260222T223021Z.jsonl`
- Validation and gates:
  - `docs/etl/sprints/AI-OPS-55/evidence/citizen_preset_codec_tests_20260222T223021Z.txt` (`31/31`)
  - `docs/etl/sprints/AI-OPS-55/evidence/explorer_gh_pages_build_20260222T223021Z.txt`
  - `docs/etl/sprints/AI-OPS-55/evidence/tracker_gate_posttrackeredit_20260222T223021Z.txt`
- CI/just markers:
  - `docs/etl/sprints/AI-OPS-55/evidence/citizen_preset_ci_bundle_history_slo_digest_heartbeat_compaction_markers_20260222T223021Z.txt`

## Outcome

- Preset heartbeat monitoring now has bounded-history compaction with strict incident preservation, reducing long-run artifact growth risk without losing red/failed chronology.
