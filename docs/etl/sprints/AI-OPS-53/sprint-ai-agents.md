# AI-OPS-53 Prompt Pack

Objective:
- Persist a tiny NDJSON heartbeat stream from digest-SLO outputs for trend-friendly contract monitoring.

Acceptance gates:
- New reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat.js`:
  - input: digest report JSON
  - output: append-only heartbeat JSONL with dedupe by stable `heartbeat_id`
  - strict fail on invalid heartbeat or `status=failed`
- New tests cover:
  - strict pass append
  - duplicate dedupe (no extra append)
  - strict fail on failed digest while still appending the row
- `justfile` adds `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat`.
- CI workflow generates + uploads heartbeat artifact:
  - `citizen-preset-contract-bundle-history-slo-digest-heartbeat`
- `just citizen-test-preset-codec` remains green.

Status update (2026-02-22):
- Heartbeat reporter shipped with append + dedupe semantics.
- Node tests added and integrated in bundle test command.
- CI now emits dedicated heartbeat artifact (JSON + JSONL).
- Strict chain + GH Pages build + tracker gate stayed green.
- evidence:
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_codec_parity_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_codec_sync_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_window_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_compaction_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_slo_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_slo_digest_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_report_20260222T221521Z.json`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_compacted_20260222T221521Z.jsonl`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_tail_20260222T221521Z.jsonl`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_tail_20260222T221521Z.jsonl`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_codec_tests_20260222T221521Z.txt`
  - `docs/etl/sprints/AI-OPS-53/evidence/explorer_gh_pages_build_20260222T221521Z.txt`
  - `docs/etl/sprints/AI-OPS-53/evidence/tracker_gate_posttrackeredit_20260222T221521Z.txt`
  - `docs/etl/sprints/AI-OPS-53/evidence/citizen_preset_ci_bundle_history_slo_digest_heartbeat_markers_20260222T221521Z.txt`
