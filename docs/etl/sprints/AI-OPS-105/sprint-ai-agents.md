# AI-OPS-105 Prompt Pack

Objective:
- Ship concern-pack outcomes heartbeat retention v1 so `/citizen` concern-pack trend monitoring can compact history safely while keeping strict parity guarantees in last-N windows.

Acceptance gates:
- Add concern-pack heartbeat compaction reporter (`scripts/report_citizen_concern_pack_outcomes_heartbeat_compaction.py`).
- Add concern-pack heartbeat compaction-window parity reporter (`scripts/report_citizen_concern_pack_outcomes_heartbeat_compaction_window.py`).
- Preserve incident classes: `failed`, `degraded`, `strict`, `malformed`, `contract_incomplete`, `weak_pack_followthrough` and `unknown_pack_select_share` threshold violations.
- Add deterministic tests for compaction preservation + compaction-window strict parity.
- Wire `just` report/check lanes and include new tests in `citizen-test-concern-pack-outcomes-heartbeat`.
- Publish strict evidence bundle under `docs/etl/sprints/AI-OPS-105/evidence/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`compaction_strict_fail_reasons=[]`, `compaction_window_status=ok`, `incident_missing_in_compacted=0`).
