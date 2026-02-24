# Citizen Preset Contract Bundle History SLO Digest (AI-OPS-52)

Date:
- 2026-02-22

## What shipped

- New compact reporter:
  - `scripts/report_citizen_preset_contract_bundle_history_slo_digest.js`
- Digest consumes the full SLO JSON and emits a stable reduced envelope:
  - `status`, `risk_level`, `risk_reasons`, `strict_fail_reasons`
  - `key_metrics`, `key_checks`, `thresholds`, `previous_window`, `deltas`

## Contract behavior

- Status mapping:
  - `failed` when `risk_level=red` (or strict-fail reasons imply hard failure)
  - `degraded` for `risk_level=amber`
  - `ok` for healthy `green`
- Strict mode:
  - non-zero on invalid digest shape
  - non-zero when digest status is `failed`

## Pipeline and CI integration

- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest`
- Workflow update:
  - `etl-tracker-gate.yml` now runs strict digest generation and uploads artifact:
    - `citizen-preset-contract-bundle-history-slo-digest`
- Test suite integration:
  - `just citizen-test-preset-codec` includes digest tests.

## Evidence

- Digest output:
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_bundle_history_slo_digest_report_20260222T220457Z.json`
  - Result: `status=ok`, `risk_level=green`, `validation_errors=[]`
- Validation and gates:
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_codec_tests_20260222T220457Z.txt` (`23/23`)
  - `docs/etl/sprints/AI-OPS-52/evidence/explorer_gh_pages_build_20260222T220457Z.txt`
  - `docs/etl/sprints/AI-OPS-52/evidence/tracker_gate_posttrackeredit_20260222T220457Z.txt`
- CI/just markers:
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_ci_bundle_history_slo_digest_markers_20260222T220457Z.txt`

## Outcome

- Preset contract monitoring now has a tiny, deterministic health artifact that is easier to consume in automation while preserving strict safety semantics from the full SLO layer.
