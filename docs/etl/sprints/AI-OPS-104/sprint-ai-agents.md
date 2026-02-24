# AI-OPS-104 Prompt Pack

Objective:
- Ship coherence-drilldown heartbeat retention v1 so `/citizen` coherence replay health keeps an incident-safe compacted history and strict raw-vs-compacted parity in last-N windows.

Acceptance gates:
- Add coherence heartbeat compaction reporter (`scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_compaction.py`).
- Add coherence heartbeat compaction-window parity reporter (`scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_compaction_window.py`).
- Preserve incident classes: `failed`, `degraded`, `strict`, `malformed`, `contract_incomplete`, replay/contract/failure threshold violations.
- Add deterministic tests for compaction preservation + compaction-window strict parity.
- Wire `just` report/check lanes and include new tests in `citizen-test-coherence-drilldown-outcomes`.
- Produce strict evidence bundle under `docs/etl/sprints/AI-OPS-104/evidence/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`compaction_strict_fail_reasons=[]`, `compaction_window_status=ok`, `incident_missing_in_compacted=0`).
