# AI-OPS-57 Kickoff

Date:
- 2026-02-22

Objective:
- Add a compact single-file digest (`ok/degraded/failed`) derived from heartbeat compaction-window parity, so alert polling can read one JSON artifact.

Primary lane (controllable):
- Citizen preset contract reliability, no upstream dependency.

Acceptance gates:
- New reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest.js` with strict mode.
- Reporter consumes compaction-window parity JSON and emits:
  - `status` + `risk_level` for alert polling
  - `risk_reasons` for soft degradation (non-incident drops)
  - `strict_fail_reasons` for hard parity failures
  - compact `key_metrics` + `key_checks`.
- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest`
- CI job `citizen-preset-contract` runs strict digest step and uploads artifact.
- `just citizen-test-preset-codec` remains green.

DoD:
- Strict report chain + build + tracker gate pass.
- Sprint artifacts captured under `docs/etl/sprints/AI-OPS-57/evidence/`.
- Tracker row and sprint index updated with references.
