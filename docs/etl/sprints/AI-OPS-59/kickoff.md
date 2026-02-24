# AI-OPS-59 Kickoff

Date:
- 2026-02-22

Objective:
- Add strict incident-preserving compaction for the compact-window digest heartbeat NDJSON stream so the newest alert lane remains bounded over time.

Primary lane (controllable):
- Citizen preset contract reliability, no upstream dependency.

Acceptance gates:
- Reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction.js` shipped with strict checks.
- Node tests include `tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction.js`.
- New just target `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact`.
- CI job `citizen-preset-contract` runs strict compaction step and uploads compaction artifact.
- `just citizen-test-preset-codec` remains green.

DoD:
- Strict report chain + build + tracker gate pass.
- Sprint artifacts captured under `docs/etl/sprints/AI-OPS-59/evidence/`.
- Tracker row and sprint index updated with references.
