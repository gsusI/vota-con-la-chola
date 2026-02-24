# AI-OPS-57 Prompt Pack

Objective:
- Add a compacted-heartbeat compact-window digest for single-file alert polling without re-reading full parity payloads.

Acceptance gates:
- Reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest.js` emits:
  - compact `status` (`ok/degraded/failed`) + `risk_level`
  - `risk_reasons` for non-incident coverage degradation
  - `strict_fail_reasons` passthrough for hard parity failures
  - `key_metrics` + `key_checks` for fast triage
- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest`
- CI update:
  - strict digest step + artifact `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window-digest`
- Test coverage:
  - strict pass (`ok`) on complete parity
  - strict pass (`degraded`) on non-incident drops
  - strict fail (`failed`) on strict parity failures

Status update (2026-02-22):
- Compact-window digest reporter shipped and integrated in `justfile` + CI workflow.
- Node tests added and passing in standalone and full codec contract suite.
- End-to-end strict chain and gates executed successfully.
- evidence:
  - `docs/etl/sprints/AI-OPS-57/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_report_20260222T224707Z.json`
  - `docs/etl/sprints/AI-OPS-57/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_report_20260222T224707Z.json`
  - `docs/etl/sprints/AI-OPS-57/evidence/citizen_preset_codec_tests_20260222T224707Z.txt`
  - `docs/etl/sprints/AI-OPS-57/evidence/explorer_gh_pages_build_20260222T224707Z.txt`
  - `docs/etl/sprints/AI-OPS-57/evidence/tracker_gate_posttrackeredit_20260222T224707Z.txt`
