# Citizen Preset Contract Bundle History SLO Digest Heartbeat (AI-OPS-53)

Date:
- 2026-02-22

## What shipped

- New heartbeat reporter:
  - `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat.js`
- Purpose:
  - append one compact row per digest run into NDJSON history
  - avoid reparsing full SLO JSON for long-horizon monitoring

## Contract behavior

- Input:
  - digest report JSON from `report_citizen_preset_contract_bundle_history_slo_digest.js`
- Output:
  - JSON append report + heartbeat row in JSONL
  - heartbeat includes `status`, `risk_level`, key metrics, reason counts, and `heartbeat_id`
- Dedupe:
  - uses stable `heartbeat_id`; duplicate inputs do not append a second line
- Strict mode:
  - fails on validation/runtime errors
  - fails when heartbeat `status=failed`
  - still appends valid failed rows to preserve incident history

## Pipeline and CI integration

- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat`
- Workflow update:
  - `etl-tracker-gate.yml` now generates and uploads:
    - `citizen-preset-contract-bundle-history-slo-digest-heartbeat`
  - artifact contains both JSON report + JSONL heartbeat stream
- Test suite update:
  - `just citizen-test-preset-codec` includes heartbeat tests.

## Evidence

- Heartbeat append report:
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_report_20260222T221521Z.json`
  - Result: `appended=true`, `duplicate_detected=false`, `history_size_after=1`, `status=ok`
- Heartbeat trail:
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_tail_20260222T221521Z.jsonl`
- Validation and gates:
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_codec_tests_20260222T221521Z.txt` (`26/26`)
  - `docs/etl/sprints/AI-OPS-53/evidence/explorer_gh_pages_build_20260222T221521Z.txt`
  - `docs/etl/sprints/AI-OPS-53/evidence/tracker_gate_posttrackeredit_20260222T221521Z.txt`
- CI/just markers:
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_ci_bundle_history_slo_digest_heartbeat_markers_20260222T221521Z.txt`

## Outcome

- The preset contract lane now exposes an append-only heartbeat feed optimized for lightweight trend polling while keeping strict quality semantics.
