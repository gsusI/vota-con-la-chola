# AI-OPS-27 Kickoff (Draft)

Objective:
- Apply one hold lane (`lane_c`) end-to-end with safety checks and publish a visible KPI delta while preserving tracker parity.

Starting inputs:
- `docs/etl/sprints/AI-OPS-26/exports/factory/import_queue.csv`
- `docs/etl/sprints/AI-OPS-26/reports/import-runbook-bcde.md`
- `docs/etl/sprints/AI-OPS-26/reports/next-sprint-trigger.md`

First tasks:
1. Validate `lane_c` patch keys + null checks and run controlled apply on `text_documents`.
2. Export post-apply KPI packet (`missing_excerpt` before/after + parity check).
3. Prepare HI adjudication packet for `lane_b` ambiguous decisions.

Active execution docs (2026-02-22 update):
- `docs/etl/sprints/AI-OPS-27/sprint-ai-agents.md`
- `docs/etl/sprints/AI-OPS-27/reports/senado-tail-status-20260222.md`
- `docs/etl/sprints/AI-OPS-27/reports/senado-tail-daemon-anti-stall-20260222.md`
- `docs/etl/sprints/AI-OPS-27/reports/initiative-doc-fetch-status-backfill-20260222.md`
- `docs/etl/sprints/AI-OPS-27/reports/initiative-doc-status-report-20260222.md`
- `docs/etl/sprints/AI-OPS-27/reports/initiative-quality-kpis-extension-20260222.md`
- `docs/etl/sprints/AI-OPS-27/reports/next-10-sprints-plan-20260222.md`
