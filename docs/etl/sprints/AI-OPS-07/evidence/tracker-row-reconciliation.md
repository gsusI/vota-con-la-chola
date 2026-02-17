# AI-OPS-07 tracker-row reconciliation note (updated)

## Scope
- Reconcile tracker wording/status after Moncloa waiver burn-down remediation.
- Keep blocker/next-command clarity for remaining PARTIAL rows.

## Applied reconciliation

### Accion ejecutiva (Consejo de Ministros)
- New tracker status: `DONE`.
- Rationale: Moncloa ingest + policy-events mapping are reproducible and SQL-derived status is `DONE` for both `moncloa_referencias` and `moncloa_rss_referencias`.
- Waiver result: Moncloa entries removed from active waiver set for AI-OPS-07.
- Evidence:
  - `docs/etl/sprints/AI-OPS-07/reports/dual-entry-apply-recompute.md`
  - `docs/etl/sprints/AI-OPS-07/reports/boe-policy-events-mapping.md`
  - `docs/etl/sprints/AI-OPS-07/evidence/post_apply_waiveraware_checker_final.log`
  - `docs/etl/sprints/AI-OPS-07/evidence/mismatch-policy-applied.json`

### Marco legal electoral
- Current tracker status: `PARTIAL`.
- Blocker: tracker contract for BOE domain is not yet finalized even though `boe_api_legal` ingest/mapping is operational.
- Next command:
  - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source boe_api_legal --snapshot-date 2026-02-16 --timeout 30 --strict-network"`

### Parlamento de Navarra
- Current tracker status: `PARTIAL`.
- Blocker: strict-network replay remains constrained; one temporary waiver stays active until `2026-02-20`.
- Next command:
  - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-16 --timeout 30 --strict-network"`

### Parlamento de Galicia
- Current tracker status: `PARTIAL`.
- Blocker: strict-network extraction still blocked; fallback remains reproducible.
- Next command:
  - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --strict-network --timeout 30"`
