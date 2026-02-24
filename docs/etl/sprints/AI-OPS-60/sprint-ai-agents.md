# AI-OPS-60 Prompt Pack

Objective:
- Guard the second-level compacted heartbeat stream with a strict last-N parity contract (`raw` vs `compacted`) including degraded incident parity.

Acceptance gates:
- Reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.js`:
  - compares `last N` rows from raw compact-window digest heartbeat vs its compacted output
  - enforces `latest` row presence in compacted stream
  - enforces parity for incidents and counts (`failed`, `degraded`, `red`)
- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact-window`
- CI update:
  - include parity-window test in Node bundle
  - strict parity-window step + artifact upload in `citizen-preset-contract` job
- Test coverage:
  - strict pass path
  - strict fail when degraded incident rows are dropped
  - strict fail when latest row is missing

Status update (2026-02-22):
- Compaction-window parity reporter shipped and integrated in `justfile` + CI workflow.
- Node tests updated and full `just citizen-test-preset-codec` passes (`48/48`).
- End-to-end strict chain and gates executed successfully.
- evidence:
  - `docs/etl/sprints/AI-OPS-60/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_report_20260222T231705Z.json`
  - `docs/etl/sprints/AI-OPS-60/evidence/citizen_preset_ci_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_markers_20260222T231705Z.txt`
  - `docs/etl/sprints/AI-OPS-60/evidence/citizen_preset_codec_tests_20260222T231705Z.txt`
  - `docs/etl/sprints/AI-OPS-60/evidence/explorer_gh_pages_build_20260222T231705Z.txt`
  - `docs/etl/sprints/AI-OPS-60/evidence/tracker_gate_posttrackeredit_20260222T231705Z.txt`
