# AI-OPS-175 — Template export lane for official procedural-review metrics

## Objetivo
Reducir fricción operativa del loop `review -> apply` en `Scenario A` generando un template CSV prellenado y compatible con el aplicador estricto (`AI-OPS-174`).

## Entregado
- Script nuevo: `scripts/export_sanction_procedural_official_review_apply_template.py`.
  - Exporta matriz `fuente oficial x KPI` con columnas listas para `apply`.
  - Prefill de `metric_key`, `source_record_id`, `source_url`, metadatos de KPI y fuente.
  - Soporta `--only-missing` para no repetir pares ya cargados.
- Lane nuevo en `justfile`:
  - `parl-export-sanction-procedural-official-review-apply-template`
- Prueba nueva:
  - `tests/test_export_sanction_procedural_official_review_apply_template.py`
- Suite actualizada:
  - `parl-test-sanction-data-catalog` ahora cubre validate/import/report/apply/template.

## Resultado de corrida (20260224T100945Z)
- Export template (`--only-missing`) en DB staging:
  - `sources_seeded_total=4/4`
  - `kpis_total=3`
  - `rows_emitted_total=12`
  - `rows_skipped_existing_total=0`
- Archivo generado:
  - `sanction_procedural_official_review_apply_template_20260224T100945Z.csv`
- Estado operativo de lane oficial tras export:
  - `status=degraded`
  - `official_review_source_metric_coverage_pct=0.0`
  - cola accionable en `4` fuentes (`status=no_metrics`)
- Tests:
  - `just parl-test-sanction-data-catalog` (`Ran 12`, OK)
  - unittest focal de template (`Ran 2`, OK)

## Conclusion operativa
El proyecto ya tiene dos piezas encadenadas y reproducibles para `Ciudadanía/Garantías`:
1) plantilla prellenada para captura manual verificable (`AI-OPS-175`),  
2) aplicación estricta con trazabilidad `source_record_pk` (`AI-OPS-174`).

Siguiente delta de valor: rellenar el template con métricas oficiales validadas y ejecutar `parl-apply-sanction-procedural-official-review-metrics` sin `dry-run`.

## Evidencia
- `docs/etl/sprints/AI-OPS-175/evidence/sanction_procedural_official_review_apply_template_20260224T100945Z.json`
- `docs/etl/sprints/AI-OPS-175/exports/sanction_procedural_official_review_apply_template_20260224T100945Z.csv`
- `docs/etl/sprints/AI-OPS-175/evidence/sanction_procedural_official_review_status_20260224T100945Z.json`
- `docs/etl/sprints/AI-OPS-175/evidence/sanction_procedural_official_review_queue_20260224T100945Z.csv`
- `docs/etl/sprints/AI-OPS-175/evidence/just_parl_export_sanction_procedural_official_review_apply_template_20260224T100945Z.txt`
- `docs/etl/sprints/AI-OPS-175/evidence/just_parl_report_sanction_procedural_official_review_status_20260224T100945Z.txt`
- `docs/etl/sprints/AI-OPS-175/evidence/just_parl_test_sanction_data_catalog_20260224T100945Z.txt`
- `docs/etl/sprints/AI-OPS-175/evidence/python_unittest_export_sanction_procedural_official_review_apply_template_20260224T100945Z.txt`
