# AI-OPS-58 Kickoff

Date:
- 2026-02-22

Objective:
- Add compact-window digest heartbeat append + window strict reporting so external alert collectors can read stable NDJSON trend and last-N status without parsing full parity payloads.

Primary lane (controllable):
- Citizen preset contract reliability, no upstream dependency.

Acceptance gates:
- New reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.js` with strict mode.
- New reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_window.js` with strict mode.
- New just targets:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat`
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-window`
- CI job `citizen-preset-contract` runs strict heartbeat + heartbeat-window steps and uploads artifacts.
- `just citizen-test-preset-codec` remains green.

DoD:
- Strict report chain + build + tracker gate pass.
- Sprint artifacts captured under `docs/etl/sprints/AI-OPS-58/evidence/`.
- Tracker row and sprint index updated with references.
