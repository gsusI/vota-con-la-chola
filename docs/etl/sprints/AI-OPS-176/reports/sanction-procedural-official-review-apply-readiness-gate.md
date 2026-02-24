# AI-OPS-176 — Readiness gate before applying official procedural metrics

## Objetivo
Evitar cargas incompletas o inconsistentes en `sanction_procedural_metrics` añadiendo una puerta de calidad explícita para el CSV de revisión manual antes del apply estricto (`AI-OPS-174`).

## Entregado
- Script nuevo: `scripts/report_sanction_procedural_official_review_apply_readiness.py`.
  - Valida cabeceras requeridas del CSV.
  - Valida IDs contra DB (`sanction_source_id`, `kpi_id`, `source_id`).
  - Valida tipos/rangos numéricos.
  - Valida coherencia de fórmula para KPIs de ratio (`value ~= numerator/denominator` con tolerancia).
  - Exporta cola accionable CSV por fila/razón.
  - Soporta `--strict` para bloquear ejecución cuando `status != ok`.
- `justfile`:
  - Nuevo lane `parl-check-sanction-procedural-official-review-apply-readiness`
  - Nuevas variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READINESS_*`
- Test nuevo:
  - `tests/test_report_sanction_procedural_official_review_apply_readiness.py`
- Suite actualizada:
  - `parl-test-sanction-data-catalog` ahora ejecuta `15` tests.

## Resultado de corrida (20260224T101432Z)
- Readiness sobre template de captura (`AI-OPS-175`) con valores vacíos:
  - `status=degraded`
  - `rows_seen=12`, `rows_ready=0`, `rows_blocked=12`
  - razones principales: `missing_required_field=12`, `missing_ratio_components=8`
  - cola exportada para ejecución manual por fila/razón
- Readiness sobre fixture completo (`AI-OPS-174`) en modo estricto:
  - `status=ok`
  - `rows_seen=4`, `rows_ready=4`, `rows_blocked=0`
- Estado del lane oficial de métricas en DB permanece:
  - `status=degraded`
  - `official_review_source_metric_coverage_pct=0.0` (aún sin carga oficial aplicada)

## Conclusion operativa
El loop de `Scenario A` queda ahora cerrado con control de calidad reproducible:
1) exportar template (`AI-OPS-175`),  
2) validar readiness (`AI-OPS-176`),  
3) aplicar en modo estricto (`AI-OPS-174`).

Siguiente paso para convertir la fila en progreso real: rellenar métricas oficiales y ejecutar `parl-check...` (strict) + `parl-apply...` sin `dry-run`.

## Evidencia
- `docs/etl/sprints/AI-OPS-176/evidence/sanction_procedural_official_review_apply_readiness_template_20260224T101432Z.json`
- `docs/etl/sprints/AI-OPS-176/exports/sanction_procedural_official_review_apply_readiness_template_queue_20260224T101432Z.csv`
- `docs/etl/sprints/AI-OPS-176/evidence/sanction_procedural_official_review_apply_readiness_fixture_20260224T101432Z.json`
- `docs/etl/sprints/AI-OPS-176/exports/sanction_procedural_official_review_apply_readiness_fixture_queue_20260224T101432Z.csv`
- `docs/etl/sprints/AI-OPS-176/evidence/sanction_procedural_official_review_status_20260224T101432Z.json`
- `docs/etl/sprints/AI-OPS-176/exports/sanction_procedural_official_review_queue_20260224T101432Z.csv`
- `docs/etl/sprints/AI-OPS-176/evidence/just_parl_check_sanction_procedural_official_review_apply_readiness_template_20260224T101432Z.txt`
- `docs/etl/sprints/AI-OPS-176/evidence/just_parl_check_sanction_procedural_official_review_apply_readiness_fixture_20260224T101432Z.txt`
- `docs/etl/sprints/AI-OPS-176/evidence/just_parl_test_sanction_data_catalog_20260224T101432Z.txt`
- `docs/etl/sprints/AI-OPS-176/evidence/python_unittest_report_sanction_procedural_official_review_apply_readiness_20260224T101432Z.txt`
