# AI-OPS-180 — Evidence traceability gate for official procedural metrics

## Objetivo
Subir el estándar de auditabilidad en `Scenario A` haciendo obligatoria la trazabilidad de evidencia por fila (`evidence_date` + `evidence_quote`) en el loop oficial `prepare -> readiness -> apply -> status`.

## Entregado
- Esquema:
  - `etl/load/sqlite_schema.sql` añade columnas en `sanction_procedural_metrics`:
    - `evidence_date`
    - `evidence_quote`
  - Compatibilidad forward en DBs viejas:
    - `etl/politicos_es/db.py` (`ensure_schema_compat`) añade ambas columnas de forma aditiva.
- Apply lane (`scripts/apply_sanction_procedural_official_review_metrics.py`):
  - requiere `evidence_date` y `evidence_quote` no vacíos;
  - valida fecha `YYYY-MM-DD`;
  - valida longitud mínima de cita (`MIN_EVIDENCE_QUOTE_LEN=20`);
  - persiste `evidence_date/evidence_quote` en `sanction_procedural_metrics`;
  - añade auto-compat local para DB vieja (`ALTER TABLE` aditivo si faltan columnas).
- Readiness lane (`scripts/report_sanction_procedural_official_review_apply_readiness.py`):
  - amplía headers requeridos con `evidence_date/evidence_quote`;
  - añade validaciones y contadores:
    - `rows_invalid_evidence_date`
    - `rows_short_evidence_quote`.
- Prepare lane (`scripts/prepare_sanction_procedural_official_review_apply_input.py`):
  - `evidence_date/evidence_quote` pasan a metadatos requeridos para fila “kept”.
- Template export (`scripts/export_sanction_procedural_official_review_apply_template.py`):
  - añade columnas `evidence_date/evidence_quote` al CSV.
- Status lane (`scripts/report_sanction_procedural_official_review_status.py`):
  - incorpora cobertura de evidencia:
    - `official_review_metric_rows_with_evidence_total`
    - `official_review_metric_rows_missing_evidence_total`
    - `official_review_evidence_coverage_pct`
    - check `official_review_evidence_chain_started`
  - nuevo estado de cola por fuente: `no_evidence_chain`
  - `next_action=backfill_evidence_date_quote_for_official_review_metrics`
  - fallback compatible con DBs antiguas sin columnas (sin romper ejecución).
- Tests:
  - se actualizan suites existentes para el nuevo contrato;
  - test nuevo de status para gap de evidencia:
    - `tests/test_report_sanction_procedural_official_review_status.py::test_report_queue_highlights_evidence_gap`
  - `parl-test-sanction-data-catalog` sube a `Ran 23`.

## Resultado de corrida (20260224T104009Z)
- Template export actualizado:
  - `rows_emitted_total=12` (incluye columnas `evidence_date/evidence_quote` vacías para captura manual).
- Unified lane (`parl-run-...prepare-apply-cycle-dry-run`) con template:
  - `exit_code=4` (esperado por `strict-prepare`)
  - `prepare=status=degraded`, `rows_kept=0`, `rows_rejected=12`
  - `cycle.apply.skipped=true`, `skip_reason=prepare_not_ok`
- Unified lane con fixture completo (incluye evidencia):
  - `prepare=status=ok`, `rows_kept=4`, `rows_rejected=0`
  - `readiness=status=ok`, `rows_ready=4`, `rows_blocked=0`
  - `apply` dry-run: `rows_ready=4`, `rows_upserted=0`, `source_record_pk_would_create=4`
- Status en staging:
  - `status=degraded`
  - `official_review_procedural_metrics_total=0`
  - `official_review_source_metric_coverage_pct=0.0`
  - `official_review_evidence_coverage_pct=0.0`
  - (degradado por falta de carga oficial real, no por fallo de pipeline).
- Tests:
  - `just parl-test-sanction-data-catalog` -> `Ran 23`, OK
  - `python -m unittest tests/test_report_sanction_procedural_official_review_status.py` -> `Ran 4`, OK
  - `python -m unittest tests/test_report_sanction_procedural_official_review_apply_readiness.py` -> `Ran 3`, OK
  - `python -m unittest tests/test_apply_sanction_procedural_official_review_metrics.py` -> `Ran 2`, OK
  - `python -m unittest tests/test_run_sanction_procedural_official_review_prepare_apply_cycle.py` -> `Ran 2`, OK

## Conclusión operativa
La lane oficial deja de aceptar métricas sin evidencia trazable. El pipeline queda listo para progreso real de cobertura con calidad auditable, manteniendo bloqueo estricto en inputs incompletos.

## Evidencia
- `docs/etl/sprints/AI-OPS-180/evidence/sanction_procedural_official_review_apply_template_20260224T104009Z.json`
- `docs/etl/sprints/AI-OPS-180/exports/sanction_procedural_official_review_apply_template_20260224T104009Z.csv`
- `docs/etl/sprints/AI-OPS-180/evidence/sanction_procedural_official_review_prepare_apply_cycle_template_exit_20260224T104009Z.json`
- `docs/etl/sprints/AI-OPS-180/evidence/sanction_procedural_official_review_apply_prepare_template_20260224T104009Z.json`
- `docs/etl/sprints/AI-OPS-180/evidence/sanction_procedural_official_review_prepare_apply_cycle_template_20260224T104009Z.json`
- `docs/etl/sprints/AI-OPS-180/evidence/sanction_procedural_official_review_apply_prepare_fixture_20260224T104009Z.json`
- `docs/etl/sprints/AI-OPS-180/evidence/sanction_procedural_official_review_prepare_apply_cycle_fixture_20260224T104009Z.json`
- `docs/etl/sprints/AI-OPS-180/evidence/sanction_procedural_official_review_status_20260224T104009Z.json`
- `docs/etl/sprints/AI-OPS-180/evidence/just_parl_run_sanction_procedural_official_review_prepare_apply_cycle_dry_run_template_20260224T104009Z.txt`
- `docs/etl/sprints/AI-OPS-180/evidence/just_parl_run_sanction_procedural_official_review_prepare_apply_cycle_dry_run_fixture_20260224T104009Z.txt`
- `docs/etl/sprints/AI-OPS-180/evidence/just_parl_test_sanction_data_catalog_20260224T104009Z.txt`
- `docs/etl/sprints/AI-OPS-180/evidence/python_unittest_report_sanction_procedural_official_review_status_20260224T104009Z.txt`
- `docs/etl/sprints/AI-OPS-180/evidence/python_unittest_report_sanction_procedural_official_review_apply_readiness_20260224T104009Z.txt`
- `docs/etl/sprints/AI-OPS-180/evidence/python_unittest_apply_sanction_procedural_official_review_metrics_20260224T104009Z.txt`
- `docs/etl/sprints/AI-OPS-180/evidence/python_unittest_run_sanction_procedural_official_review_prepare_apply_cycle_20260224T104009Z.txt`
