# AI-OPS-186 — Export `apply-ready` remediation CSV from KPI-gap queue

## Objetivo
Reducir fricción operativa en `Scenario A` transformando la cola por par `fuente x KPI` en un CSV directamente consumible por el loop `readiness -> apply`.

## Entregado
- `scripts/export_sanction_procedural_official_review_apply_from_kpi_gap_queue.py`
  - consume la cola generada por `export_sanction_procedural_official_review_kpi_gap_queue.py`.
  - exporta CSV con contrato de apply + metadatos de backlog:
    - `queue_key`
    - `queue_status`
    - `queue_priority`
    - `queue_next_action`
  - soporta:
    - scope temporal (`--period-date`, `--period-granularity`)
    - filtro por estados (`--statuses`)
    - `--include-ready`
    - gate `--strict-actionable`.
  - prefill automático de filas existentes con cadena parcial:
    - para `missing_source_record` / `missing_evidence` recupera `value/numerator/denominator/source_record_pk/source_record_id` desde `sanction_procedural_metrics` + `source_records`.
    - para `missing_metric` deja campos de carga vacíos.
- `justfile`
  - lane nuevo: `parl-export-sanction-procedural-official-review-apply-from-kpi-gap-queue`.
  - variables nuevas: `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_*`.
  - integrado en `parl-sanction-data-catalog-pipeline`.
- Tests
  - `tests/test_export_sanction_procedural_official_review_apply_from_kpi_gap_queue.py` (`Ran 3`).
  - `parl-test-sanction-data-catalog` sube a `Ran 38`.

## Resultado de corrida (20260224T112006Z)
- Staging real (`period_date=2025-12-31`, `period_granularity=year`):
  - `status=ok` (export lane), `queue_report_status=degraded` (backlog pendiente real).
  - `queue_rows_seen_total=12`
  - `rows_emitted_total=12`
  - `rows_emitted_by_status={missing_metric:12}`
- Corrida vía `just`:
  - misma contabilidad y salida funcional.
- Fixture contractual mixto:
  - `queue_rows_seen_total=11`
  - `rows_emitted_total=11`
  - `rows_emitted_by_status={missing_metric:9, missing_source_record:1, missing_evidence:1}`
  - confirma prefill de chain gaps:
    - `missing_source_record`: conserva `value/numerator/denominator`.
    - `missing_evidence`: conserva `source_record_pk/source_record_id` y deja evidencia para completar.
- Tests:
  - `just parl-test-sanction-data-catalog` -> `Ran 38`, OK.
  - `just parl-sanction-data-catalog-pipeline` -> OK (incluye lane nuevo `apply-from-kpi-gap-queue` en flujo real).

## Conclusión operativa
La lane oficial ahora tiene puente directo `diagnóstico -> plantilla de remediación -> apply`, sin manipulación manual intermedia de columnas. Esto acelera cierre del backlog por KPI y mantiene trazabilidad por fila.

## Evidencia
- `docs/etl/sprints/AI-OPS-186/evidence/sanction_procedural_official_review_apply_from_gap_queue_20260224T112006Z.json`
- `docs/etl/sprints/AI-OPS-186/evidence/sanction_procedural_official_review_apply_from_gap_queue_via_just_20260224T112006Z.json`
- `docs/etl/sprints/AI-OPS-186/evidence/sanction_procedural_official_review_apply_from_gap_queue_fixture_mixed_20260224T112006Z.json`
- `docs/etl/sprints/AI-OPS-186/exports/sanction_procedural_official_review_apply_from_gap_queue_20260224T112006Z.csv`
- `docs/etl/sprints/AI-OPS-186/exports/sanction_procedural_official_review_apply_from_gap_queue_via_just_20260224T112006Z.csv`
- `docs/etl/sprints/AI-OPS-186/exports/sanction_procedural_official_review_apply_from_gap_queue_fixture_mixed_20260224T112006Z.csv`
- `docs/etl/sprints/AI-OPS-186/evidence/just_parl_export_sanction_procedural_official_review_apply_from_kpi_gap_queue_20260224T112006Z.txt`
- `docs/etl/sprints/AI-OPS-186/evidence/just_parl_test_sanction_data_catalog_20260224T112006Z.txt`
- `docs/etl/sprints/AI-OPS-186/evidence/just_parl_sanction_data_catalog_pipeline_20260224T112006Z.txt`
