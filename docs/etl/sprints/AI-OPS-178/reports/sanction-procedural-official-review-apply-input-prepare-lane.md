# AI-OPS-178 — Prepare lane for official procedural-review apply input

## Objetivo
Permitir carga incremental segura desde plantillas de captura (`AI-OPS-175`) filtrando filas vacías antes del ciclo estricto (`AI-OPS-177`).

## Entregado
- Script nuevo: `scripts/prepare_sanction_procedural_official_review_apply_input.py`.
  - Filtra filas sin `value` o sin metadatos mínimos requeridos.
  - Exporta:
    - CSV preparado (`rows_kept`) para apply,
    - CSV de rechazadas con `_csv_line/_reason`,
    - resumen JSON con cobertura y checks.
  - Soporta `--strict` (`exit=4` cuando `status != ok`).
- `justfile`:
  - Nuevo lane `parl-prepare-sanction-procedural-official-review-apply-input`.
  - Nuevas variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_*`.
- Test nuevo:
  - `tests/test_prepare_sanction_procedural_official_review_apply_input.py`.

## Resultado de corrida (20260224T102145Z)
- Sobre template de captura (`AI-OPS-175`):
  - `status=degraded`
  - `rows_seen=12`, `rows_kept=0`, `rows_rejected=12`
- Sobre fixture completo (`AI-OPS-174`):
  - `status=ok`
  - `rows_seen=4`, `rows_kept=4`, `rows_rejected=0`
- Estado lane oficial en staging:
  - se mantiene `degraded`
  - `official_review_source_metric_coverage_pct=0.0` (sin carga real en este slice)

## Conclusión operativa
El flujo manual deja de depender de edición ad hoc de CSV:
`template -> prepare -> (readiness/apply cycle)`.
Esto habilita carga parcial reproducible sin romper el gate estricto.

## Evidencia
- `docs/etl/sprints/AI-OPS-178/evidence/sanction_procedural_official_review_apply_prepare_template_20260224T102145Z.json`
- `docs/etl/sprints/AI-OPS-178/evidence/sanction_procedural_official_review_apply_prepare_fixture_20260224T102145Z.json`
- `docs/etl/sprints/AI-OPS-178/exports/sanction_procedural_official_review_apply_prepared_template_20260224T102145Z.csv`
- `docs/etl/sprints/AI-OPS-178/exports/sanction_procedural_official_review_apply_rejected_template_20260224T102145Z.csv`
- `docs/etl/sprints/AI-OPS-178/exports/sanction_procedural_official_review_apply_prepared_fixture_20260224T102145Z.csv`
- `docs/etl/sprints/AI-OPS-178/exports/sanction_procedural_official_review_apply_rejected_fixture_20260224T102145Z.csv`
- `docs/etl/sprints/AI-OPS-178/evidence/just_parl_prepare_sanction_procedural_official_review_apply_input_template_20260224T102145Z.txt`
- `docs/etl/sprints/AI-OPS-178/evidence/just_parl_prepare_sanction_procedural_official_review_apply_input_fixture_20260224T102145Z.txt`
- `docs/etl/sprints/AI-OPS-178/evidence/python_unittest_prepare_sanction_procedural_official_review_apply_input_20260224T102145Z.txt`
- `docs/etl/sprints/AI-OPS-178/evidence/just_parl_test_sanction_data_catalog_20260224T102145Z.txt`
