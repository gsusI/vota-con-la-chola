# AI-OPS-181 — Raw-to-KPI transformer for official procedural review metrics

## Objetivo
Reducir fricción manual en `Scenario A` para poblar `sanction_procedural_metrics`: pasar de captura KPI por fila a captura raw por fuente (`presentados/estimados/anulaciones/p90`) y generar automáticamente el CSV `apply-ready` con trazabilidad de evidencia.

## Entregado
- Script nuevo: `scripts/export_sanction_procedural_official_review_apply_from_raw_metrics.py`
  - Entrada: CSV raw por fuente/periodo con campos de evidencia (`evidence_date`, `evidence_quote`).
  - Salida: CSV `apply-ready` con 3 KPIs por fila raw:
    - `kpi:recurso_estimation_rate`
    - `kpi:formal_annulment_rate`
    - `kpi:resolution_delay_p90_days`
  - Cálculo automático de ratios (`estimados/presentados`, `anulaciones/presentados`), generación de `metric_key`, `source_record_id` por KPI y `raw_row_key` para traza.
  - Cola de rechazo reproducible por fila (`_csv_line`, `_reason`, `_priority`).
  - Validaciones previas al loop de apply:
    - headers requeridos,
    - fecha de evidencia `YYYY-MM-DD`,
    - cita mínima (`>=20` chars),
    - counts numéricos válidos,
    - `recurso_presentado_count > 0`,
    - `resolution_delay_p90_days > 0`,
    - componentes no negativos,
    - ratios en `[0,1]`,
    - no duplicar `metric_key`.
- `justfile`
  - nuevo lane: `parl-export-sanction-procedural-official-review-apply-from-raw`
  - nuevas variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_*`.
- Tests
  - nuevo: `tests/test_export_sanction_procedural_official_review_apply_from_raw_metrics.py`
  - `parl-test-sanction-data-catalog` sube a `Ran 26` en verde.

## Resultado de corrida (20260224T104837Z)
- Transformación raw -> apply:
  - `status=ok`
  - `rows_seen=4`
  - `rows_emitted=4`
  - `kpi_rows_emitted=12`
  - `rows_rejected=0`
- Readiness sobre salida transformada:
  - `status=ok`
  - `rows_seen=12`
  - `rows_ready=12`
  - `rows_blocked=0`
- Ciclo unificado (`prepare -> readiness -> apply`) en `--dry-run`:
  - `prepare=status=ok`
  - `readiness=status=ok`
  - apply dry-run `rows_ready=12`, `source_record_pk_would_create=12`
- Estado global lane oficial (staging) permanece `degraded` (`official_review_procedural_metrics_total=0`) porque en este slice no se hizo carga real, solo cierre de fricción/contrato.

## Conclusión operativa
El cuello de botella pasa de “carga KPI manual repetitiva” a “captura raw por fuente con evidencia”. El loop estricto existente (`AI-OPS-180`) ahora puede alimentarse con menos error humano y menor tiempo de preparación.

## Evidencia
- `docs/etl/sprints/AI-OPS-181/evidence/sanction_procedural_official_review_apply_from_raw_20260224T104837Z.json`
- `docs/etl/sprints/AI-OPS-181/inputs/sanction_procedural_official_review_raw_fixture_20260224T104837Z.csv`
- `docs/etl/sprints/AI-OPS-181/exports/sanction_procedural_official_review_apply_from_raw_20260224T104837Z.csv`
- `docs/etl/sprints/AI-OPS-181/evidence/sanction_procedural_official_review_apply_readiness_from_raw_20260224T104837Z.json`
- `docs/etl/sprints/AI-OPS-181/evidence/sanction_procedural_official_review_prepare_apply_cycle_from_raw_20260224T104837Z.json`
- `docs/etl/sprints/AI-OPS-181/evidence/sanction_procedural_official_review_status_20260224T104837Z.json`
- `docs/etl/sprints/AI-OPS-181/evidence/just_parl_export_sanction_procedural_official_review_apply_from_raw_20260224T104837Z.txt`
- `docs/etl/sprints/AI-OPS-181/evidence/just_parl_test_sanction_data_catalog_20260224T104837Z.txt`
