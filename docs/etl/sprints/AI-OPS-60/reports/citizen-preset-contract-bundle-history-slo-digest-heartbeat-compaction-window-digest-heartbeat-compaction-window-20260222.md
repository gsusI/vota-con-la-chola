# Citizen Preset Compact-Window Digest Heartbeat Compaction-Window Parity Report (AI-OPS-60)

Date:
- 2026-02-22

Scope:
- Add strict parity checks between raw and compacted compact-window digest heartbeat streams over `last N` rows.

What shipped:
- New reporter:
  - `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.js`
- New tests:
  - `tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.js`
- New just target:
  - `citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact-window`
- CI wiring:
  - strict compaction-window parity step + artifact in `.github/workflows/etl-tracker-gate.yml`

Strict run snapshot (`20260222T231705Z`):
- `window_raw_entries=2`
- `missing_in_compacted_in_window=0`
- `incident_missing_in_compacted=0`
- `raw_window_failed=0`, `failed_present_in_compacted=0`
- `raw_window_degraded=0`, `degraded_present_in_compacted=0`
- `strict_fail_reasons=[]`

Evidence:
- `docs/etl/sprints/AI-OPS-60/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_report_20260222T231705Z.json`
- `docs/etl/sprints/AI-OPS-60/evidence/citizen_preset_ci_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_markers_20260222T231705Z.txt`
