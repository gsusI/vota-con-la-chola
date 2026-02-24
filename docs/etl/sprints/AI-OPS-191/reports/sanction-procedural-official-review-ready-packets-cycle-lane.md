# AI-OPS-191 - Ready-packets cycle lane (`ready subset -> raw/prepare/apply`)

## Objetivo
Habilitar progreso incremental en `Scenario A`: cargar automáticamente las fuentes oficiales que ya tengan paquete raw completo, sin bloquearse por paquetes todavía incompletos.

## Entregado
- `scripts/run_sanction_procedural_official_review_ready_packets_cycle.py`
  - toma `--packets-dir` + cola KPI y ejecuta diagnóstico de readiness por paquete;
  - selecciona solo paquetes `ready_for_transform=true`;
  - fusiona subset listo en CSV raw y ejecuta ciclo estricto existente (`raw -> prepare -> readiness -> apply`);
  - soporta gates operativos:
    - `--strict-actionable` (falla si no hay backlog esperado),
    - `--strict-min-ready` + `--min-ready-packets` (falla si no hay mínimo de paquetes listos),
    - passthrough `--strict-raw/--strict-prepare/--strict-readiness`;
  - skip reasons deterministas:
    - `no_actionable_packets`
    - `no_ready_packets`
    - `ready_packets_below_minimum`
- `justfile`
  - variables nuevas `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_*`;
  - lanes nuevas:
    - `parl-run-sanction-procedural-official-review-ready-packets-cycle`
    - `parl-run-sanction-procedural-official-review-ready-packets-cycle-dry-run`
  - integración de lane dry-run en `parl-sanction-data-catalog-pipeline`.
- Tests
  - `tests/test_run_sanction_procedural_official_review_ready_packets_cycle.py` (`Ran 3`).
  - `parl-test-sanction-data-catalog` sube a `Ran 53`.

## Resultado de corrida
- Staging (`AI-OPS-188/latest`, `period=2026-02-12/year`, `dry-run`):
  - `progress.status=degraded`
  - `packets_expected_total=4`, `packets_ready_total=0` (`invalid_row=4`)
  - ciclo salta explícito con `skip_reason=no_ready_packets`.
- Fixture contractual (`AI-OPS-189` paquetes completos, `period=2025-12-31/year`, strict + dry-run):
  - `progress.status=ok`, `packets_ready_total=4/4`
  - `ready_packets_selected_total=4`
  - ciclo estricto pasa completo:
    - `raw.status=ok`
    - `prepare.status=ok`
    - `readiness.status=ok`
    - `apply.rows_ready=12` (`rows_upserted=0` por dry-run)
- Integración:
  - `just parl-run-sanction-procedural-official-review-ready-packets-cycle-dry-run` -> `OK`
  - `just parl-sanction-data-catalog-pipeline` -> `OK`
  - `just parl-test-sanction-data-catalog` -> `Ran 53`, `OK`

## Conclusión operativa
La lane oficial ya no depende de “todo o nada”: cuando una fuente esté lista, puede cargarse en el mismo ciclo reproducible sin esperar a las demás. Esto reduce tiempo muerto y mantiene avance controlable de cobertura oficial.

## Evidencia
- `docs/etl/sprints/AI-OPS-191/evidence/sanction_procedural_official_review_ready_packets_cycle_20260224T120343Z.json`
- `docs/etl/sprints/AI-OPS-191/evidence/sanction_procedural_official_review_ready_packets_cycle_progress_20260224T120343Z.json`
- `docs/etl/sprints/AI-OPS-191/evidence/sanction_procedural_official_review_ready_packets_cycle_cycle_20260224T120343Z.json`
- `docs/etl/sprints/AI-OPS-191/evidence/sanction_procedural_official_review_ready_packets_cycle_fixture_20260224T120343Z.json`
- `docs/etl/sprints/AI-OPS-191/evidence/sanction_procedural_official_review_ready_packets_cycle_progress_fixture_20260224T120343Z.json`
- `docs/etl/sprints/AI-OPS-191/evidence/sanction_procedural_official_review_ready_packets_cycle_cycle_fixture_20260224T120343Z.json`
- `docs/etl/sprints/AI-OPS-191/evidence/just_parl_run_sanction_procedural_official_review_ready_packets_cycle_dry_run_20260224T120359Z.txt`
- `docs/etl/sprints/AI-OPS-191/evidence/just_parl_sanction_data_catalog_pipeline_20260224T120359Z.txt`
- `docs/etl/sprints/AI-OPS-191/evidence/just_parl_test_sanction_data_catalog_20260224T120359Z.txt`
- `docs/etl/sprints/AI-OPS-191/exports/sanction_procedural_official_review_raw_from_ready_packets_20260224T120343Z.csv`
- `docs/etl/sprints/AI-OPS-191/exports/sanction_procedural_official_review_raw_from_ready_packets_fixture_20260224T120343Z.csv`
