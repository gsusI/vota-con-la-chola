# AI-OPS-187 — One-command `gap -> apply` cycle for official procedural review

## Objetivo
Automatizar el cierre de gaps encadenados (`missing_source_record` primero) sin pasos manuales entre diagnóstico de cola y apply.

## Entregado
- `scripts/run_sanction_procedural_official_review_apply_from_kpi_gap_cycle.py`
  - ejecuta en una corrida:
    - export desde cola KPI (`build_apply_rows_from_gap_queue`)
    - `readiness -> apply -> status` (reutilizando `run_cycle`)
  - soporta:
    - filtro por estado (`--statuses`, default `missing_source_record`)
    - scope temporal (`--period-date`, `--period-granularity`)
    - `--strict-actionable` (falla cuando no hay filas accionables)
    - `--strict-readiness`, `--dry-run`.
  - semántica explícita de skip:
    - `skip_reason=no_actionable_rows` cuando no hay filas del estado objetivo.
- `justfile`
  - lanes:
    - `parl-run-sanction-procedural-official-review-apply-from-kpi-gap-cycle`
    - `parl-run-sanction-procedural-official-review-apply-from-kpi-gap-cycle-dry-run`
  - variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_*`.
  - integración en `parl-sanction-data-catalog-pipeline` (dry-run).
- Tests
  - `tests/test_run_sanction_procedural_official_review_apply_from_kpi_gap_cycle.py` (`Ran 3`).
  - `parl-test-sanction-data-catalog` sube a `Ran 41`.

## Resultado de corrida (20260224T112750Z)
- Staging real (`period=2025-12-31/year`, `statuses=missing_source_record`, dry-run):
  - `gap_export.status=degraded`
  - `rows_emitted_total=0`
  - `rows_skipped_filtered_status_total=12` (todo el backlog actual está en `missing_metric`)
  - ciclo salta con `skip_reason=no_actionable_rows` (sin reintento ciego).
- Corrida vía `just`:
  - mismo comportamiento y contabilidad.
- Fixture contractual (`missing_source_record=1`, no dry-run):
  - `gap_export.status=ok`
  - `rows_emitted_total=1`
  - `readiness.status=ok`
  - `apply.rows_ready=1`
  - `apply.rows_upserted=1`
  - confirma cierre automático de cadena `source_record_pk` para métricas ya existentes.
- Tests:
  - `just parl-test-sanction-data-catalog` -> `Ran 41`, OK.
  - `just parl-sanction-data-catalog-pipeline` -> OK con lane nuevo integrado.

## Conclusión operativa
`Scenario A` gana un lane automatizado para remediar chain gaps en lote y, cuando no existen filas del estado objetivo, se detiene con señal explícita en lugar de gastar ciclos.

## Evidencia
- `docs/etl/sprints/AI-OPS-187/evidence/sanction_procedural_official_review_gap_cycle_20260224T112750Z.json`
- `docs/etl/sprints/AI-OPS-187/evidence/sanction_procedural_official_review_gap_cycle_via_just_20260224T112750Z.json`
- `docs/etl/sprints/AI-OPS-187/evidence/sanction_procedural_official_review_gap_cycle_fixture_missing_source_record_20260224T112750Z.json`
- `docs/etl/sprints/AI-OPS-187/evidence/sanction_procedural_official_review_gap_cycle_pipeline_20260224T112750Z.json`
- `docs/etl/sprints/AI-OPS-187/exports/sanction_procedural_official_review_apply_from_gap_cycle_20260224T112750Z.csv`
- `docs/etl/sprints/AI-OPS-187/exports/sanction_procedural_official_review_apply_from_gap_cycle_via_just_20260224T112750Z.csv`
- `docs/etl/sprints/AI-OPS-187/exports/sanction_procedural_official_review_apply_from_gap_cycle_fixture_missing_source_record_20260224T112750Z.csv`
- `docs/etl/sprints/AI-OPS-187/evidence/just_parl_run_sanction_procedural_official_review_apply_from_kpi_gap_cycle_dry_run_20260224T112750Z.txt`
- `docs/etl/sprints/AI-OPS-187/evidence/just_parl_sanction_data_catalog_pipeline_20260224T112750Z.txt`
- `docs/etl/sprints/AI-OPS-187/evidence/just_parl_test_sanction_data_catalog_20260224T112750Z.txt`
