# AI-OPS-60 Kickoff

Date:
- 2026-02-22

Objective:
- Add strict parity-window checks for the compact-window digest heartbeat compaction lane so raw-vs-compacted integrity remains auditable as this second-level stream grows.

Primary lane (controllable):
- Citizen preset contract reliability, no upstream dependency.

Acceptance gates:
- New reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.js` with strict mode.
- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact-window`
- CI job `citizen-preset-contract` runs strict compaction-window parity step and uploads artifact.
- `just citizen-test-preset-codec` remains green.

DoD:
- Strict report chain + build + tracker gate pass.
- Sprint artifacts captured under `docs/etl/sprints/AI-OPS-60/evidence/`.
- Tracker row and sprint index updated with references.
