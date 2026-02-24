# AI-OPS-98 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add KPI trend heartbeat coverage so regressions in core citizen KPIs are detectable through strict, reproducible last-N window contracts.

Definition of done:
- KPI heartbeat reporter appends deduped JSONL rows from product KPI digest.
- Window reporter enforces strict thresholds for failed/degraded/contract-incomplete and KPI-threshold violations.
- Dedicated tests and `just` lanes are green and integrated in release regression.
- Sprint evidence/docs are published under `docs/etl/sprints/AI-OPS-98/`.
