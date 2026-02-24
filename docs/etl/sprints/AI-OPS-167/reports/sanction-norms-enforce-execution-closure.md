# AI-OPS-167 — Cierre de cobertura de ejecucion en rol `enforce`

## Objetivo
Ejecutar el siguiente lote pendiente del tracker para cerrar el gap residual de ejecución en `enforce` y dejar la cobertura de ejecución completa (`15/15`) dentro del lane `Responsabilidad por fragmento normativo`.

## Alcance ejecutado
- `roles=enforce` en:
  - `scripts/backfill_sanction_norms_execution_lineage_evidence.py`
  - `scripts/backfill_sanction_norms_execution_evidence.py`
  - `scripts/backfill_sanction_norms_procedural_metric_evidence.py`
- Recalculo de estado:
  - `scripts/report_sanction_norms_seed_status.py`
  - `scripts/export_sanction_norms_seed_source_record_upgrade_queue.py`
  - `PRAGMA foreign_key_check`
- Validación de suite:
  - `just parl-test-sanction-norms-seed`
  - `just parl-test-liberty-restrictions`

## Corrida de cierre (DB real)
Timestamp: `20260224T015316Z`

### 1) Lineage bridge (`roles=enforce`)
- `responsibilities_scanned_total=4`
- `responsibilities_with_lineage_match_total=4`
- `observation_links_total=7`
- `evidence_inserted=7`
- `source_record_pk_resolved_total=7`
- `by_match_method={shared_related_norm:4, delegate_to_observed_direct:1, direct_norm_match:2}`

### 2) Ejecucion directa (`roles=enforce`)
- `observations_scanned_total=7`
- `observations_with_responsibility_total=2`
- `evidence_inserted=0`
- `evidence_updated=2`

### 3) Métricas procedimentales (`roles=enforce`)
- `metrics_scanned_total=6`
- `metrics_with_fragment_candidates_total=6`
- `metrics_with_responsibility_total=0`
- `evidence_inserted=0`
- `evidence_updated=0`

## Estado agregado tras el lote
- `responsibility_evidence_items_total=73` (antes `66`)
- `responsibility_evidence_items_execution_total=36` (antes `29`)
- `responsibilities_with_execution_evidence_total=15/15` (antes `13/15`)
- `responsibility_execution_coverage_pct=1.0` (antes `0.866667`)
- Cobertura por rol de ejecución:
  - `approve=6/6`
  - `propose=3/3`
  - `delegate=2/2`
  - `enforce=4/4`
- `responsibility_evidence_items_with_non_seed_source_record_total=73`
- Cola `seed->non-seed`: `queue_rows_total=0`
- `PRAGMA foreign_key_check`: `0` filas

## Validacion
- `just parl-test-sanction-norms-seed` -> `Ran 25`, `OK`
- `just parl-test-liberty-restrictions` -> `Ran 100`, `OK (skipped=1)`

## Evidencia
- `docs/etl/sprints/AI-OPS-167/evidence/sanction_norms_execution_lineage_evidence_backfill_20260224T015316Z.json`
- `docs/etl/sprints/AI-OPS-167/evidence/sanction_norms_execution_evidence_backfill_20260224T015316Z.json`
- `docs/etl/sprints/AI-OPS-167/evidence/sanction_norms_procedural_metric_evidence_backfill_20260224T015316Z.json`
- `docs/etl/sprints/AI-OPS-167/evidence/sanction_norms_seed_status_20260224T015316Z.json`
- `docs/etl/sprints/AI-OPS-167/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T015316Z.json`
- `docs/etl/sprints/AI-OPS-167/evidence/sqlite_fk_check_20260224T015316Z.txt`
- `docs/etl/sprints/AI-OPS-167/evidence/just_parl_test_sanction_norms_seed_20260224T015316Z.txt`
- `docs/etl/sprints/AI-OPS-167/evidence/just_parl_test_liberty_restrictions_20260224T015316Z.txt`

## Siguiente paso sugerido
Con ejecución ya cerrada (`15/15`), priorizar el gap parlamentario por responsabilidad (`parliamentary=8/15`, `parliamentary_vote=6/15`) y paralelamente preparar fuente oficial para garantías procedimentales fuera de semilla (TEAR/TEAC/contencioso/defensores).
