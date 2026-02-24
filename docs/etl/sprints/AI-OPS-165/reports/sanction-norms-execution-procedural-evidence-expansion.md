# AI-OPS-165 — Expansion de evidencia de ejecucion y garantias procedimentales

## Objetivo
Escalar la cadena `norma -> fragmento -> responsabilidad` fuera de `enforce` y añadir una segunda senal de expediente (metricas procedimentales) sin depender de nuevas fuentes externas.

## Cambios implementados
- `scripts/backfill_sanction_norms_execution_evidence.py`
  - Se opera con roles ampliados (`enforce,approve,propose,delegate`) desde `justfile`.
- `scripts/backfill_sanction_norms_procedural_metric_evidence.py` (nuevo)
  - Materializa evidencia `other` con `record_kind=sanction_norm_procedural_metric_evidence_backfill`.
  - Cruza `sanction_procedural_metrics` con fragmentos observados por `sanction_source_id` en `sanction_volume_observations` y aplica matching por rol en `legal_fragment_responsibilities`.
  - Resuelve `source_record_pk` por `boe_ref:<BOE-ID>` cuando procede.
- `justfile`
  - Nuevo lane: `parl-backfill-sanction-norms-procedural-metric-evidence`.
  - Defaults de ejecución ampliados a roles `enforce,approve,propose,delegate`.
  - `parl-test-sanction-norms-seed` incluye el test nuevo.
- Tests
  - Nuevo: `tests/test_backfill_sanction_norms_procedural_metric_evidence.py`.
  - `tests/test_report_sanction_norms_seed_status.py` añade regresión para contar evidencia procedimental como señal de ejecución.

## Corrida de cierre (DB real)
Timestamp: `20260224T013817Z`

### Backfill ejecucion (roles ampliados)
- `observations_scanned_total=7`
- `observations_with_responsibility_total=7`
- `evidence_inserted=11`
- `evidence_updated=2`
- `by_role={approve:7, propose:4, enforce:2}`

### Backfill procedimental (nuevo lane)
- `metrics_scanned_total=6`
- `metrics_with_fragment_candidates_total=6`
- `metrics_with_responsibility_total=6`
- `evidence_inserted=12`
- `source_record_pk_resolved_total=12`
- `by_role={approve:9, propose:3}`
- `by_kpi={kpi:recurso_estimation_rate:2, kpi:formal_annulment_rate:2, kpi:resolution_delay_p90_days:2}`

### Estado agregado lane sancionador
- `responsibility_evidence_items_total=62` (antes `39`)
- `responsibility_evidence_items_execution_total=25` (antes `2`)
- `responsibilities_with_execution_evidence_total=11/15` (antes `2/15`)
- `responsibility_execution_coverage_pct=0.733333` (antes `0.133333`)
- `responsibility_evidence_item_execution_share_pct=0.403226`
- `responsibility_evidence_items_with_non_seed_source_record_total=62`
- Cola `seed->non-seed`: `queue_rows_total=0`
- `PRAGMA foreign_key_check`: `0` filas

## Validacion
- `just parl-test-sanction-norms-seed` -> `Ran 23`, `OK`
- `just parl-test-liberty-restrictions` -> `Ran 100`, `OK (skipped=1)`

## Evidencia
- `docs/etl/sprints/AI-OPS-165/evidence/sanction_norms_execution_evidence_backfill_20260224T013817Z.json`
- `docs/etl/sprints/AI-OPS-165/evidence/sanction_norms_procedural_metric_evidence_backfill_20260224T013817Z.json`
- `docs/etl/sprints/AI-OPS-165/evidence/sanction_norms_seed_status_20260224T013817Z.json`
- `docs/etl/sprints/AI-OPS-165/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T013817Z.json`
- `docs/etl/sprints/AI-OPS-165/evidence/sqlite_fk_check_20260224T013817Z.txt`
- `docs/etl/sprints/AI-OPS-165/evidence/just_parl_test_sanction_norms_seed_20260224T013817Z.txt`
- `docs/etl/sprints/AI-OPS-165/evidence/just_parl_test_liberty_restrictions_20260224T013817Z.txt`

## Siguiente paso sugerido
Cubrir el gap residual de `delegate` (0/2 responsabilidades con evidencia de ejecución) con evidencia primaria de actos delegados y ventanas persona/cargo por organismo.
