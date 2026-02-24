# AI-OPS-58 Prompt Pack

Objective:
- Extend compact-window digest lane with append-only heartbeat NDJSON and strict last-N window status checks.

Acceptance gates:
- Reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.js`:
  - appends deduped heartbeat rows from compact-window digest
  - preserves strict status semantics (`failed` exits non-zero in strict mode)
- Reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_window.js`:
  - summarizes `last N` with counts/rates for `failed` and `degraded`
  - enforces configurable strict thresholds for both lanes
- New just targets:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat`
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-window`
- CI update:
  - strict heartbeat + window steps + artifacts
- Test coverage:
  - heartbeat append pass/dedupe/fail
  - heartbeat-window pass/degraded-fail/malformed-fail

Status update (2026-02-22):
- Compact-window digest heartbeat + window reporters shipped and integrated in `justfile` + CI workflow.
- Node tests added and passing in standalone and full codec contract suite.
- End-to-end strict chain and gates executed successfully.
- evidence:
  - `docs/etl/sprints/AI-OPS-58/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_report_20260222T225515Z.json`
  - `docs/etl/sprints/AI-OPS-58/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_window_report_20260222T225515Z.json`
  - `docs/etl/sprints/AI-OPS-58/evidence/citizen_preset_codec_tests_20260222T225515Z.txt`
  - `docs/etl/sprints/AI-OPS-58/evidence/explorer_gh_pages_build_20260222T225515Z.txt`
  - `docs/etl/sprints/AI-OPS-58/evidence/tracker_gate_posttrackeredit_20260222T225515Z.txt`
