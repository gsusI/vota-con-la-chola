# AI-OPS-185 — Cola accionable por par `fuente x KPI` para revisión procedimental oficial

## Objetivo
Convertir la cola por fuente en una cola operativa más precisa por par `sanction_source_id x kpi_id`, para priorizar remediación y evitar falsas señales de progreso.

## Entregado
- `scripts/export_sanction_procedural_official_review_kpi_gap_queue.py`
  - exporta cola reproducible por par esperado (`4 fuentes x 3 KPIs`).
  - clasifica cada fila en:
    - `missing_source`
    - `missing_metric`
    - `missing_source_record`
    - `missing_evidence`
    - `ready`
  - añade `queue_key` estable, `metric_key_expected`, `priority`, `next_action`.
  - soporta scope temporal (`--period-date`, `--period-granularity`), `--include-ready`, `--queue-limit` y `--strict-empty`.
- `justfile`
  - nuevo lane: `parl-export-sanction-procedural-official-review-kpi-gap-queue`.
  - nuevas variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_KPI_GAP_*`.
  - integración del lane en `parl-sanction-data-catalog-pipeline`.
- Tests
  - nuevo archivo: `tests/test_export_sanction_procedural_official_review_kpi_gap_queue.py` (`Ran 3`).
  - `parl-test-sanction-data-catalog` sube a `Ran 35`.

## Resultado de corrida (20260224T111300Z)
- Staging real (`period_date=2025-12-31`, `period_granularity=year`):
  - `status=degraded`
  - `expected_pairs_total=12`
  - `pairs_ready_total=0`
  - `pairs_missing_metric_total=12`
  - `pairs_missing_source_record_total=0`
  - `pairs_missing_evidence_total=0`
  - `queue_rows_total=12`
- Corrida vía `just`:
  - misma contabilidad y estado que la corrida directa.
- Fixture contractual mixto (`include_ready=true`):
  - `status=degraded`
  - `expected_pairs_total=12`
  - `pairs_ready_total=1`
  - `pairs_missing_metric_total=9`
  - `pairs_missing_source_record_total=1`
  - `pairs_missing_evidence_total=1`
  - valida discriminación de gaps por par (`missing_metric` vs cadena incompleta `source_record/evidence`).
- Tests:
  - `just parl-test-sanction-data-catalog` -> `Ran 35`, OK.

## Conclusión operativa
La lane oficial ahora tiene una cola de trabajo granular y priorizable por KPI, no solo por fuente. Esto permite planificar captura/corrección por unidad mínima verificable y medir avance real hacia cobertura completa.

## Evidencia
- `docs/etl/sprints/AI-OPS-185/evidence/sanction_procedural_official_review_kpi_gap_queue_20260224T111300Z.json`
- `docs/etl/sprints/AI-OPS-185/evidence/sanction_procedural_official_review_kpi_gap_queue_via_just_20260224T111300Z.json`
- `docs/etl/sprints/AI-OPS-185/evidence/sanction_procedural_official_review_kpi_gap_queue_fixture_mixed_20260224T111300Z.json`
- `docs/etl/sprints/AI-OPS-185/exports/sanction_procedural_official_review_kpi_gap_queue_20260224T111300Z.csv`
- `docs/etl/sprints/AI-OPS-185/exports/sanction_procedural_official_review_kpi_gap_queue_via_just_20260224T111300Z.csv`
- `docs/etl/sprints/AI-OPS-185/evidence/just_parl_export_sanction_procedural_official_review_kpi_gap_queue_20260224T111300Z.txt`
- `docs/etl/sprints/AI-OPS-185/evidence/just_parl_test_sanction_data_catalog_20260224T111300Z.txt`
