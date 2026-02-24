# AI-OPS-179 — Unified `prepare -> apply cycle` lane

## Objetivo
Eliminar glue manual entre `AI-OPS-178` y `AI-OPS-177` para ejecutar en una sola corrida:
`prepare -> readiness -> apply -> status`.

## Entregado
- Script nuevo: `scripts/run_sanction_procedural_official_review_prepare_apply_cycle.py`.
  - Ejecuta `prepare` del CSV de entrada.
  - Si `--strict-prepare` y `prepare != ok`, bloquea con `skip_reason=prepare_not_ok` (exit `4`).
  - Si pasa, ejecuta el ciclo existente (`AI-OPS-177`) sobre el CSV preparado.
  - Emite artefactos separados: `prepare`, `cycle`, `status`, y payload consolidado.
- Refactor reusable:
  - `scripts/run_sanction_procedural_official_review_apply_cycle.py` expone `run_cycle(...)` para reutilizar lógica sin duplicación.
- `justfile`:
  - Nuevos lanes:
    - `parl-run-sanction-procedural-official-review-prepare-apply-cycle`
    - `parl-run-sanction-procedural-official-review-prepare-apply-cycle-dry-run`
  - Nuevas variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_CYCLE_*`.
- Tests:
  - Nuevo: `tests/test_run_sanction_procedural_official_review_prepare_apply_cycle.py`.
  - Mejora: tests de ciclo suprimen stdout JSON masivo para mantener logs legibles.
  - `parl-test-sanction-data-catalog` actualizado a `22` tests.

## Resultado de corrida (20260224T102733Z)
- Ruta template vacío (`strict-prepare`, dry-run):
  - `exit_code=4`
  - `prepare=status=degraded` (`rows_seen=12`, `rows_kept=0`, `rows_rejected=12`)
  - `cycle.apply.skipped=true`, `skip_reason=prepare_not_ok`
- Ruta fixture completo (`strict-prepare`, dry-run):
  - `prepare=status=ok` (`rows_seen=4`, `rows_kept=4`, `rows_rejected=0`)
  - `readiness=status=ok` (`rows_ready=4`, `rows_blocked=0`)
  - `apply` dry-run (`rows_ready=4`, `rows_upserted=0`, `source_record_pk_would_create=4`)
- Estado lane oficial en staging:
  - `status=degraded`
  - `official_review_source_metric_coverage_pct=0.0` (no carga real en este slice)
- Tests:
  - `just parl-test-sanction-data-catalog` -> `Ran 22`, OK
  - unittest ciclo prepare/apply -> `Ran 2`, OK
  - unittest ciclo base -> `Ran 2`, OK
  - unittest prepare input -> `Ran 3`, OK

## Conclusión operativa
El flujo operativo queda unificado para `Scenario A`:
`template/parcial -> prepare -> strict cycle`.
Se reduce riesgo humano y se mantiene bloqueo estricto cuando la captura no está lista.

## Evidencia
- `docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_template_exit_20260224T102733Z.json`
- `docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_template_20260224T102733Z.json`
- `docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_cycle_template_20260224T102733Z.json`
- `docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_status_template_20260224T102733Z.json`
- `docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_fixture_20260224T102733Z.json`
- `docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_cycle_fixture_20260224T102733Z.json`
- `docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_status_fixture_20260224T102733Z.json`
- `docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_apply_prepare_template_20260224T102733Z.json`
- `docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_apply_prepare_fixture_20260224T102733Z.json`
- `docs/etl/sprints/AI-OPS-179/exports/sanction_procedural_official_review_apply_prepared_template_20260224T102733Z.csv`
- `docs/etl/sprints/AI-OPS-179/exports/sanction_procedural_official_review_apply_rejected_template_20260224T102733Z.csv`
- `docs/etl/sprints/AI-OPS-179/exports/sanction_procedural_official_review_apply_prepared_fixture_20260224T102733Z.csv`
- `docs/etl/sprints/AI-OPS-179/exports/sanction_procedural_official_review_apply_rejected_fixture_20260224T102733Z.csv`
- `docs/etl/sprints/AI-OPS-179/evidence/just_parl_run_sanction_procedural_official_review_prepare_apply_cycle_dry_run_template_20260224T102733Z.txt`
- `docs/etl/sprints/AI-OPS-179/evidence/just_parl_run_sanction_procedural_official_review_prepare_apply_cycle_dry_run_fixture_20260224T102733Z.txt`
- `docs/etl/sprints/AI-OPS-179/evidence/just_parl_test_sanction_data_catalog_20260224T102733Z.txt`
- `docs/etl/sprints/AI-OPS-179/evidence/python_unittest_run_sanction_procedural_official_review_prepare_apply_cycle_20260224T102733Z.txt`
- `docs/etl/sprints/AI-OPS-179/evidence/python_unittest_run_sanction_procedural_official_review_apply_cycle_20260224T102733Z.txt`
- `docs/etl/sprints/AI-OPS-179/evidence/python_unittest_prepare_sanction_procedural_official_review_apply_input_20260224T102733Z.txt`
