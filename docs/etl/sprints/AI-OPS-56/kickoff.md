# AI-OPS-56 Kickoff

Date:
- 2026-02-22

Objective:
- Add strict parity checks between raw heartbeat NDJSON and compacted heartbeat NDJSON over a last-N window to detect accidental over-pruning.

Primary lane (controllable):
- Citizen preset contract reliability, no upstream dependency.

Acceptance gates:
- New reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window.js` with strict mode.
- Reporter validates in `last N`:
  - latest raw row still present in compacted
  - incident parity (`failed`/`red`/strict-fail/malformed rows are not dropped)
  - failed/red counts are not underreported in compacted window view
- `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window` added with configurable env vars.
- CI job `citizen-preset-contract` runs strict compaction-window report and uploads artifact.
- `just citizen-test-preset-codec` remains green.

DoD:
- Strict report chain + build + tracker gate pass.
- Sprint artifacts captured under `docs/etl/sprints/AI-OPS-56/evidence/`.
- Tracker row and sprint index updated with references.
