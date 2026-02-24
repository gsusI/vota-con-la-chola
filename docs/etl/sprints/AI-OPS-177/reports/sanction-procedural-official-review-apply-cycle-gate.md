# AI-OPS-177 — Strict apply cycle lane (`readiness -> apply -> status`)

## Objetivo
Eliminar pasos manuales y riesgo operativo en `Scenario A` unificando el ciclo de carga de métricas oficiales en una sola ejecución reproducible con gate estricto.

## Entregado
- Script nuevo: `scripts/run_sanction_procedural_official_review_apply_cycle.py`.
  - Ejecuta en orden:
    1) readiness del CSV (`AI-OPS-176`),
    2) apply de métricas (`AI-OPS-174`) si readiness `ok`,
    3) estado lane oficial antes/después.
  - En `--strict-readiness` bloquea apply cuando readiness no está en `ok` (exit `4`).
  - Emite artefacto JSON consolidado del ciclo.
- `justfile`:
  - `parl-apply-sanction-procedural-official-review-metrics` y `...-dry-run` pasan a usar el ciclo estricto.
- Test nuevo:
  - `tests/test_run_sanction_procedural_official_review_apply_cycle.py`
- Suite actualizada:
  - `parl-test-sanction-data-catalog` ahora ejecuta `17` tests.

## Resultado de corrida (20260224T101854Z)
- Ruta bloqueada (template vacío, strict, dry-run):
  - `exit_code=4` (esperado)
  - readiness `degraded` (`rows_seen=12`, `rows_ready=0`, `rows_blocked=12`)
  - apply `skipped=true`, `skip_reason=readiness_not_ok`
- Ruta válida (fixture completo, strict, dry-run):
  - readiness `ok` (`rows_ready=4/4`, `rows_blocked=0`)
  - apply ejecutado en dry-run (`rows_ready=4`, `rows_upserted=0`, `source_record_pk_would_create=4`)
- Estado lane oficial en DB staging:
  - se mantiene `degraded`
  - `official_review_source_metric_coverage_pct=0.0` (sin carga real aplicada en este slice)
- Tests:
  - `just parl-test-sanction-data-catalog` -> `Ran 17`, OK
  - unittest ciclo -> `Ran 2`, OK

## Conclusion operativa
El loop de `Ciudadanía/Garantías` queda operativo y más seguro:
`template -> readiness -> strict cycle apply`.
A partir de aquí, el siguiente progreso de cobertura depende de rellenar métricas oficiales reales y correr el ciclo en modo no dry-run.

## Evidencia
- `docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_apply_cycle_template_exit_20260224T101854Z.json`
- `docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_apply_cycle_template_20260224T101854Z.json`
- `docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_apply_cycle_status_template_20260224T101854Z.json`
- `docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_apply_cycle_fixture_20260224T101854Z.json`
- `docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_apply_cycle_status_fixture_20260224T101854Z.json`
- `docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_apply_readiness_template_20260224T101854Z.json`
- `docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_apply_readiness_fixture_20260224T101854Z.json`
- `docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_status_20260224T101854Z.json`
- `docs/etl/sprints/AI-OPS-177/evidence/just_parl_apply_sanction_procedural_official_review_metrics_dry_run_template_20260224T101854Z.txt`
- `docs/etl/sprints/AI-OPS-177/evidence/just_parl_apply_sanction_procedural_official_review_metrics_dry_run_fixture_20260224T101854Z.txt`
- `docs/etl/sprints/AI-OPS-177/evidence/just_parl_test_sanction_data_catalog_20260224T101854Z.txt`
- `docs/etl/sprints/AI-OPS-177/evidence/python_unittest_run_sanction_procedural_official_review_apply_cycle_20260224T101854Z.txt`
