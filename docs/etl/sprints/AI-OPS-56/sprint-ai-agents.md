# AI-OPS-56 Prompt Pack

Objective:
- Detect heartbeat over-pruning by checking parity between raw and compacted heartbeat streams in strict mode.

Acceptance gates:
- Reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window.js` emits:
  - raw/compacted totals and raw-window coverage
  - `missing_raw_ids_sample`, `missing_incident_ids_sample`
  - checks for `latest_present_ok`, `incident_parity_ok`, `failed_parity_ok`, `red_parity_ok`
  - strict failure reasons when parity drifts
- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window`
- CI update:
  - strict compaction-window step + artifact `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window`
- Test coverage:
  - strict pass when compacted preserves raw last-N parity
  - strict fail when incident row is missing in compacted
  - strict fail when latest raw row is missing in compacted

Status update (2026-02-22):
- Compaction-window parity reporter shipped and integrated in `justfile` + CI workflow.
- Node tests added and passing in standalone and full codec contract suite.
- End-to-end strict chain and gates executed successfully.
- evidence:
  - `docs/etl/sprints/AI-OPS-56/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_report_20260222T223944Z.json`
  - `docs/etl/sprints/AI-OPS-56/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_report_20260222T223944Z.json`
  - `docs/etl/sprints/AI-OPS-56/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compacted_20260222T223944Z.jsonl`
  - `docs/etl/sprints/AI-OPS-56/evidence/citizen_preset_codec_tests_20260222T223944Z.txt`
  - `docs/etl/sprints/AI-OPS-56/evidence/explorer_gh_pages_build_20260222T223944Z.txt`
  - `docs/etl/sprints/AI-OPS-56/evidence/tracker_gate_posttrackeredit_20260222T223944Z.txt`
