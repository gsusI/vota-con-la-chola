# AI-OPS-54 Prompt Pack

Objective:
- Add strict last-N heartbeat window monitoring on top of digest heartbeat NDJSON.

Acceptance gates:
- New reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_window.js` emits:
  - `status_counts`, `risk_level_counts`
  - `failed_in_window`, `failed_rate_pct`
  - `first_failed_run_at`, `last_failed_run_at`
  - `first_red_risk_run_at`, `last_red_risk_run_at`
  - `latest`, `checks`, `strict_fail_reasons`
- `--strict` fails when:
  - empty window
  - malformed rows present
  - failed count/rate exceed thresholds
  - latest status is failed
- `justfile` exposes `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-window`.
- `.github/workflows/etl-tracker-gate.yml` runs strict heartbeat-window report and uploads `citizen-preset-contract-bundle-history-slo-digest-heartbeat-window`.
- `just citizen-test-preset-codec` remains green.

Status update (2026-02-22):
- Heartbeat-window reporter shipped with strict checks and timestamped failed/red boundaries.
- Node tests added for strict pass, strict fail-by-threshold/latest, and strict fail-by-malformed row.
- CI artifacts extended with heartbeat-window report.
- Strict chain + GH Pages build + tracker gate stayed green.
- evidence:
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_codec_parity_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_codec_sync_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_window_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_compaction_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_slo_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_slo_digest_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_window_report_20260222T222156Z.json`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_compacted_20260222T222156Z.jsonl`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_tail_20260222T222156Z.jsonl`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_tail_20260222T222156Z.jsonl`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_codec_tests_20260222T222156Z.txt`
  - `docs/etl/sprints/AI-OPS-54/evidence/explorer_gh_pages_build_20260222T222156Z.txt`
  - `docs/etl/sprints/AI-OPS-54/evidence/tracker_gate_posttrackeredit_20260222T222156Z.txt`
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_ci_bundle_history_slo_digest_heartbeat_window_markers_20260222T222156Z.txt`
