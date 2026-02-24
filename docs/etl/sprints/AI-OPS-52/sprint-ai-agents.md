# AI-OPS-52 Prompt Pack

Objective:
- Add a compact strict digest layer on top of preset bundle-history SLO output for low-friction machine polling.

Acceptance gates:
- New reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest.js` consumes SLO JSON and emits:
  - `status` (`ok|degraded|failed`)
  - `risk_level` (`green|amber|red`)
  - `risk_reasons`, `strict_fail_reasons`
  - `key_metrics`, `key_checks`, `thresholds`, `previous_window`, `deltas`
- `--strict` fails on invalid digest or failed status.
- `justfile` exposes `just citizen-report-preset-contract-bundle-history-slo-digest`.
- `.github/workflows/etl-tracker-gate.yml` runs digest generation and uploads artifact `citizen-preset-contract-bundle-history-slo-digest`.
- `just citizen-test-preset-codec` remains green.

Status update (2026-02-22):
- Digest reporter shipped with strict contract and deterministic shape.
- Node tests added for strict green and strict red paths.
- CI job and artifact upload updated for digest stage.
- Strict chain + GH Pages build + tracker gate stayed green.
- evidence:
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_report_20260222T220457Z.json`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_codec_parity_report_20260222T220457Z.json`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_codec_sync_report_20260222T220457Z.json`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_bundle_report_20260222T220457Z.json`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_bundle_history_report_20260222T220457Z.json`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_bundle_history_window_report_20260222T220457Z.json`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_bundle_history_compaction_report_20260222T220457Z.json`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_bundle_history_slo_report_20260222T220457Z.json`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_bundle_history_slo_digest_report_20260222T220457Z.json`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_bundle_history_compacted_20260222T220457Z.jsonl`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_contract_bundle_history_tail_20260222T220457Z.jsonl`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_codec_tests_20260222T220457Z.txt`
  - `docs/etl/sprints/AI-OPS-52/evidence/explorer_gh_pages_build_20260222T220457Z.txt`
  - `docs/etl/sprints/AI-OPS-52/evidence/tracker_gate_posttrackeredit_20260222T220457Z.txt`
  - `docs/etl/sprints/AI-OPS-52/evidence/citizen_preset_ci_bundle_history_slo_digest_markers_20260222T220457Z.txt`
