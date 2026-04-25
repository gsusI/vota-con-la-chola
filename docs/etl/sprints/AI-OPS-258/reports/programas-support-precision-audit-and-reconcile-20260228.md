# AI-OPS-258 — Auditoría de precisión + reconciliación de `programas_partidos`

## Objetivo
Cerrar la auditoría de precisión abierta tras AI-OPS-257 y eliminar falsos positivos confirmados sin abrir deuda manual en `topic_evidence_reviews`.

## Cambios aplicados
- Auditoría manual estratificada de `support` en `BNG/VOX/FORO/PP`.
- Hardening semántico en `declared_stance`:
  - se elimina el nominal suelto `reduccion` (fuente de TOC false positives),
  - se añade forma contextual `reduccion de(l|la|los|las)` para preservar casos programáticos válidos.
- Nuevo modo operativo en ETL: `backfill-declared-stance --reconcile-no-signal` para degradar automáticamente a `unclear` stances auto-asignados (`declared:regex_v*`) que ya no tienen señal.
- Recompute completo: `backfill-declared-positions` + `backfill-combined-positions` + `quality-report` + `e2e_tracker_status` enforce.

## Resultado
- Precisión auditada (muestra estratificada): `35/36 = 0.9722` (`>= 0.90`, PASS).
- Cierre de falsos positivos TOC confirmados en VOX:
  - `evidence_id=1560859` -> `unclear`
  - `evidence_id=1561009` -> `unclear`
- Estado final `programas_partidos` (staging):
  - `support: 392 -> 390`
  - `unclear: 172 -> 174`
  - `review_pending: 0`
  - gate declarado: `passed=true`
  - tracker enforce: `mismatches=0`, `done_zero_real=0`

## Evidencia principal
- Auditoría:
  - `docs/etl/sprints/AI-OPS-258/exports/programas_support_precision_stratified_sample_20260228.csv`
  - `docs/etl/sprints/AI-OPS-258/evidence/programas_support_precision_audit_summary_20260228.json`
  - `docs/etl/sprints/AI-OPS-258/exports/programas_support_precision_audit_breakdown_20260228.csv`
- Reconciliación y estado final:
  - `docs/etl/sprints/AI-OPS-258/evidence/programas_backfill_declared_stance_post_precision_reconcile_20260228.json`
  - `docs/etl/sprints/AI-OPS-258/evidence/programas_declared_status_post_precision_reconcile_20260228.json`
  - `docs/etl/sprints/AI-OPS-258/evidence/quality_declared_programas_post_precision_reconcile_20260228.json`
  - `docs/etl/sprints/AI-OPS-258/evidence/tracker_status_post_precision_reconcile_enforce_20260228.log`
- Evidencia de filas TOC post-reconcile:
  - `docs/etl/sprints/AI-OPS-258/exports/programas_vox_toc_false_positive_candidates_post_reconcile_20260228.csv`
- Tests:
  - `docs/etl/sprints/AI-OPS-258/evidence/unittest_parl_declared_stance_precision_reconcile_20260228.txt`
  - `docs/etl/sprints/AI-OPS-258/evidence/unittest_parl_programas_partidos_precision_reconcile_20260228.txt`

## Comandos reproducibles
```bash
python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db etl/data/staging/politicos-es.db --source-id programas_partidos --min-auto-confidence 0.62 --reconcile-no-signal
python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db etl/data/staging/politicos-es.db --source-id programas_partidos --as-of-date 2026-02-28
python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db etl/data/staging/politicos-es.db --as-of-date 2026-02-28
python3 scripts/ingestar_parlamentario_es.py quality-report --db etl/data/staging/politicos-es.db --include-declared --declared-source-ids programas_partidos --skip-vote-gate --enforce-gate --json-out docs/etl/sprints/AI-OPS-258/evidence/quality_declared_programas_post_precision_reconcile_20260228.json
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real
```
