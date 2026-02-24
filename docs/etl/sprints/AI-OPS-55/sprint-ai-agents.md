# AI-OPS-55 Prompt Pack

Objective:
- Bound heartbeat NDJSON growth with deterministic compaction while preserving alert-critical rows.

Acceptance gates:
- Reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction.js` emits:
  - `entries_total/selected/dropped`, `selected_ratio`
  - `failed_*`, `red_*`, `incidents_*`, `malformed_*`
  - cadence/tier summary + selected reason samples
  - strict checks (`latest_selected`, no dropped incidents, drop-at-scale rule)
- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact`
- CI update:
  - strict heartbeat-compaction step + artifact `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction`
- Test coverage:
  - keep incident entries + write compacted JSONL
  - strict fail when no rows are dropped above threshold

Status update (2026-02-22):
- Heartbeat compaction reporter implemented and integrated in `justfile` + CI workflow.
- Node tests added and passing in standalone and full codec contract suite.
- End-to-end strict chain and gates executed successfully.
- evidence:
  - `docs/etl/sprints/AI-OPS-55/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_report_20260222T223021Z.json`
  - `docs/etl/sprints/AI-OPS-55/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compacted_20260222T223021Z.jsonl`
  - `docs/etl/sprints/AI-OPS-55/evidence/citizen_preset_codec_tests_20260222T223021Z.txt`
  - `docs/etl/sprints/AI-OPS-55/evidence/explorer_gh_pages_build_20260222T223021Z.txt`
  - `docs/etl/sprints/AI-OPS-55/evidence/tracker_gate_posttrackeredit_20260222T223021Z.txt`
