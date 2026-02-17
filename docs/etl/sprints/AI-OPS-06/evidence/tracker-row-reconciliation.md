# AI-OPS-06 tracker row reconciliation

## Inputs used
- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-06/exports/mismatch_candidates.csv`
- `docs/etl/sprints/AI-OPS-06/reports/mismatch-policy-apply-recompute.md`

## Reconciled rows

### 1) Accion ejecutiva (Consejo de Ministros)
- Done now: `NO` (`PARTIAL`).
- Current blocker: mismatch between tracker partial status and SQL done state for `moncloa_referencias` + `moncloa_rss_referencias`, now documented as temporary `WAIVED_MISMATCH` with policy artifact.
- Evidence evidence: `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json` and `docs/etl/sprints/AI-OPS-06/reports/mismatch-policy-apply-recompute.md`.
- Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --strict-network --timeout 30`.

### 2) Parlamento de Navarra
- Done now: `NO` (`PARTIAL`).
- Current blocker: `403` en `--strict-network`; reproducible fallback en `--from-file`; mismatch currently waived via policy set.
- Evidence files: `docs/etl/sprints/AI-OPS-06/exports/mismatch_candidates.csv`, `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json`, y `docs/etl/sprints/AI-OPS-06/reports/mismatch-policy-apply-recompute.md`.
- Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --strict-network --timeout 30`.

## No-change row

### Parlamento de Galicia
- No status change was applied.
- Reason: mismatch candidates/evidence provided for this pass do not include `parlamento_galicia_deputados`; no new evidence was introduced to justify changing the existing 403/fallback status/text.

## Escalation check
- Unresolved mismatch source IDs in strict unwaived path remain in the policy gate output and are tracked in the policy report.
- For unresolved status context, see: `docs/etl/sprints/AI-OPS-06/reports/mismatch-policy-apply-recompute.md`.
