# AI-OPS-08 Tracker row reconciliation evidence

## Scope
- Reconciled tracker wording for legal/executive + blocked-source rows after `waiver-burndown-apply-recompute`.
- Inputs: `docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md`, `docs/etl/sprints/AI-OPS-08/exports/tracker_contract_candidates.csv`, `docs/etl/e2e-scrape-load-tracker.md`.

## Row updates

### Marco legal electoral
- Source mapping: `boe_api_legal`
- Done now: YES
- Blocker: none
- Siguiente comando: `just etl-tracker-gate`
- Evidence: `docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md`, `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-boe-ingest-replay.log`, `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-boe-policy-events-backfill.log`, `docs/etl/sprints/AI-OPS-08/reports/boe-tracker-mapping-hardening.md`.

### Accion ejecutiva (Consejo de Ministros)
- Done now: YES (no evidence change this cycle)
- Blocker: none
- Siguiente comando: `just etl-tracker-gate`
- Evidence retained: `docs/etl/sprints/AI-OPS-07/reports/dual-entry-apply-recompute.md`, `docs/etl/sprints/AI-OPS-07/reports/boe-policy-events-mapping.md`

### Parlamento de Navarra
- Source mapping: `parlamento_navarra_parlamentarios_forales`
- Done now: NO
- Blocker: `--strict-network` still returns HTTP 403; row remains `PARTIAL` in tracker and SQL (`PARTIAL/PARTIAL`) without active waiver.
- Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-16 --strict-network --timeout 30`
- Evidence: `docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md`, `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-probe-navarra-strict.log`, `docs/etl/mismatch-waivers.json`.

### Parlamento de Galicia
- Source mapping: `parlamento_galicia_deputados`
- Done now: NO
- Blocker: `--strict-network` probe remains HTTP 403; no deterministic next-state movement available in this cycle.
- Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --snapshot-date 2026-02-16 --strict-network --timeout 30`
- Evidence: `docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md`, `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-probe-galicia-strict.log`.

## Escalation notes
- `Marco legal electoral` was promoted to `DONE` with reproducible BOE ingest/backfill evidence.
- Navarra remains unresolved due strict-network blocker (`HTTP 403`) but no longer requires active waiver for gate parity.
