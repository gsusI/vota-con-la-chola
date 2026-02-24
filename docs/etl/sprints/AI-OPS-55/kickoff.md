# AI-OPS-55 Kickoff

Date:
- 2026-02-22

Objective:
- Add deterministic compaction for the SLO digest heartbeat stream so long-run JSONL growth stays bounded while preserving alert-relevant chronology (`failed`/`red`/strict incidents).

Primary lane (controllable):
- Citizen preset contract reliability, no upstream dependency.

Acceptance gates:
- New reporter `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction.js` with strict mode.
- Compaction keeps latest and incident entries (`failed`, `red`, malformed, strict-fail rows).
- `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact` added with configurable policy/env vars.
- CI job `citizen-preset-contract` runs strict heartbeat compaction report and uploads artifact.
- `just citizen-test-preset-codec` remains green.

DoD:
- Strict report chain + build + tracker gate pass.
- Sprint artifacts captured under `docs/etl/sprints/AI-OPS-55/evidence/`.
- Tracker row and sprint index updated with references.
