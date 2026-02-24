# AI-OPS-174 — Apply loop for official procedural-review metrics (TEAR/TEAC/contencioso/defensor)

## Objetivo
Cerrar el gap operativo entre la cola accionable (`AI-OPS-173`) y la escritura trazable en `sanction_procedural_metrics`, con un loop reproducible `CSV review/apply` bajo `just`.

## Entregado
- Script nuevo: `scripts/apply_sanction_procedural_official_review_metrics.py`.
  - Valida contrato mínimo de fila (`sanction_source_id`, `kpi_id`, `period_date`, `source_url`, `value`).
  - Verifica FKs (`sanction_volume_sources`, `sanction_procedural_kpi_definitions`, `sources`).
  - Soporta `--dry-run` y `--strict`.
  - Resuelve/crea `source_record_pk` automáticamente cuando se provee `source_id/source_record_id`.
  - Upsert idempotente por `metric_key`.
- Prueba nueva: `tests/test_apply_sanction_procedural_official_review_metrics.py`.
- Lanes nuevos en `justfile`:
  - `parl-apply-sanction-procedural-official-review-metrics`
  - `parl-apply-sanction-procedural-official-review-metrics-dry-run`
- `parl-test-sanction-data-catalog` integra el test nuevo.

## Resultado de corrida (20260224T100608Z)
- Dry-run estricto sobre fixture de 4 fuentes oficiales:
  - `rows_seen=4`
  - `rows_ready=4`
  - `skipped_* = 0` (sin filas inválidas)
  - `source_record_pk_would_create=4`
- Estado de lane oficial tras dry-run (sin mutación de DB):
  - `status=degraded`
  - `official_review_source_seed_coverage_pct=1.0`
  - `official_review_source_metric_coverage_pct=0.0`
  - Cola accionable sigue en `4` filas (`status=no_metrics`)

## Conclusion operativa
El loop `review -> apply` queda productivo y verificable en modo estricto, con trazabilidad de `source_record_pk` y contrato de upsert listo para ingestar métricas oficiales reales. El estado funcional del lane no cambia aún porque esta corrida fue de validación `dry-run` (sin carga efectiva de datos oficiales).

## Evidencia
- `docs/etl/sprints/AI-OPS-174/evidence/sanction_procedural_official_review_apply_20260224T100608Z.json`
- `docs/etl/sprints/AI-OPS-174/evidence/sanction_procedural_official_review_status_20260224T100608Z.json`
- `docs/etl/sprints/AI-OPS-174/evidence/sanction_procedural_official_review_queue_20260224T100608Z.csv`
- `docs/etl/sprints/AI-OPS-174/evidence/just_parl_apply_sanction_procedural_official_review_metrics_dry_run_20260224T100608Z.txt`
- `docs/etl/sprints/AI-OPS-174/evidence/just_parl_report_sanction_procedural_official_review_status_20260224T100608Z.txt`
- `docs/etl/sprints/AI-OPS-174/evidence/just_parl_test_sanction_data_catalog_20260224T100608Z.txt`
- `docs/etl/sprints/AI-OPS-174/evidence/python_unittest_apply_sanction_procedural_official_review_metrics_20260224T100608Z.txt`
- `docs/etl/sprints/AI-OPS-174/inputs/sanction_procedural_official_review_metrics_apply_fixture_20260224T100608Z.csv`
