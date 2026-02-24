# AI-OPS-106 Prompt Pack

Objective:
- Ship trust-action nudges heartbeat retention v1 so `/citizen` trust-action trend monitoring can compact history safely while keeping strict parity guarantees in last-N windows.

Acceptance gates:
- Add trust-action heartbeat compaction reporter (`scripts/report_citizen_trust_action_nudges_heartbeat_compaction.py`).
- Add trust-action heartbeat compaction-window parity reporter (`scripts/report_citizen_trust_action_nudges_heartbeat_compaction_window.py`).
- Preserve incident classes: `failed`, `degraded`, `strict`, `malformed`, `contract_incomplete`, and `nudge_clickthrough` threshold violations.
- Add deterministic tests for compaction preservation + compaction-window strict parity.
- Wire `just` report/check lanes and include new tests in `citizen-test-trust-action-nudges-heartbeat`.
- Publish strict evidence bundle under `docs/etl/sprints/AI-OPS-106/evidence/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`compaction_strict_fail_reasons=[]`, `compaction_window_status=ok`, `incident_missing_in_compacted=0`).
