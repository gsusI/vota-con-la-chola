# AI-OPS-59 Prompt Pack

Objective:
- Keep the compact-window digest heartbeat lane operationally bounded with deterministic compaction that never drops incident rows.

Acceptance gates:
- Reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction.js`:
  - compacts NDJSON with configurable cadence windows
  - always keeps oldest/latest anchors
  - preserves incident rows (`failed`, `degraded`, `red`, malformed, strict-fail markers)
- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact`
- CI update:
  - test list includes new compaction test
  - strict compaction step + uploaded artifact for this lane
- Test coverage:
  - strict pass with degraded/failed/red incident preservation
  - strict fail when no entries are dropped above threshold

Status update (2026-02-22):
- Compact-window digest heartbeat compaction reporter shipped and integrated in `justfile` + CI workflow.
- Node tests updated and full `just citizen-test-preset-codec` passes (`45/45`).
- End-to-end strict chain and gates executed successfully.
- evidence:
  - `docs/etl/sprints/AI-OPS-59/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_report_20260222T230747Z.json`
  - `docs/etl/sprints/AI-OPS-59/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compacted_20260222T230747Z.jsonl`
  - `docs/etl/sprints/AI-OPS-59/evidence/citizen_preset_codec_tests_20260222T230747Z.txt`
  - `docs/etl/sprints/AI-OPS-59/evidence/explorer_gh_pages_build_20260222T230747Z.txt`
  - `docs/etl/sprints/AI-OPS-59/evidence/tracker_gate_posttrackeredit_20260222T230747Z.txt`
