# AI-OPS-189 - One-command `packet-dir -> raw cycle` lane

## Objetivo
Cerrar el salto operativo entre paquetes raw por fuente (`AI-OPS-188`) y el ciclo estricto de carga (`raw -> prepare -> readiness -> apply`) sin ensamblado manual de CSV.

## Entregado
- `scripts/run_sanction_procedural_official_review_raw_packets_cycle.py`
  - consume un directorio de paquetes por fuente (`--packets-dir`) y la cola KPI (`build_raw_packets_from_gap_queue`) para:
    - validar cobertura esperada por paquete,
    - fusionar paquetes a un único raw CSV (`--raw-in-out`),
    - ejecutar el ciclo existente (`run_sanction_procedural_official_review_raw_prepare_apply_cycle.py`).
  - gates explícitos:
    - `--strict-actionable` (falla si no hay paquetes accionables),
    - `--strict-packet-coverage` (falla si faltan paquetes o headers),
    - passthrough de `--strict-raw/--strict-prepare/--strict-readiness`.
  - semántica de skip reproducible:
    - `packet_plan_failed`
    - `no_actionable_packets`
    - `missing_packet_files` / `invalid_packet_headers`
    - `no_packet_rows`
  - salida consolidada:
    - `packet_input` (cobertura, filas cargadas, faltantes/extra),
    - `cycle` (raw/prepare/readiness/apply/status).
- `justfile`
  - variables nuevas `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_*`.
  - lanes nuevas:
    - `parl-run-sanction-procedural-official-review-raw-packets-cycle`
    - `parl-run-sanction-procedural-official-review-raw-packets-cycle-dry-run`
  - integración en `parl-sanction-data-catalog-pipeline` (dry-run).
  - `parl-test-sanction-data-catalog` incorpora test nuevo.
- Tests
  - `tests/test_run_sanction_procedural_official_review_raw_packets_cycle.py` (`Ran 3`).
  - suite `parl-test-sanction-data-catalog` sube a `Ran 47`.

## Resultado de corrida (20260224T114727Z)
- Staging directo (`packets-dir` generado en AI-OPS-188, `period=2025-12-31/year`, `statuses=missing_metric`, `dry-run`):
  - `packet_input.status=ok`
  - `packets_expected_total=4`
  - `packet_files_found_total=4`
  - `packet_files_missing_total=0`
  - `packet_rows_loaded_total=4`
  - ciclo interno sobre paquetes vacíos queda `raw=degraded`, `prepare=degraded`, `readiness=failed`, `rows_ready=0` (sin carga efectiva, esperado en plantillas no completadas).
- Corrida vía `just` (`20260224T114738Z`):
  - misma contabilidad y comportamiento (`4/4` paquetes detectados, `rows_ready=0`).
- Fixture contractual estricto (`20260224T114814Z`, paquetes completados con evidencia y métricas):
  - `packet_input.status=ok` con `4/4` paquetes y `4` filas raw.
  - ciclo estricto (`strict-packet-coverage + strict-raw + strict-prepare + strict-readiness`, dry-run):
    - `raw.status=ok`
    - `prepare.status=ok`
    - `readiness.status=ok`
    - `apply.rows_ready=12`
    - `apply.rows_upserted=0` (dry-run).
- Tests / pipeline:
  - `just parl-test-sanction-data-catalog` -> `Ran 47`, `OK`.
  - `just parl-sanction-data-catalog-pipeline` -> `OK` con lane AI-OPS-189 integrada.

## Conclusión operativa
`Scenario A` ya tiene un comando reproducible para pasar de paquetes por fuente a ciclo de carga completo. El equipo solo completa los CSV por fuente; el resto del flujo queda automatizado y auditable.

## Evidencia
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_20260224T114727Z.json`
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_packets_20260224T114727Z.json`
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_cycle_20260224T114727Z.json`
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_via_just_20260224T114738Z.json`
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_packets_via_just_20260224T114738Z.json`
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_cycle_via_just_20260224T114738Z.json`
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_fixture_20260224T114814Z.json`
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_packets_fixture_20260224T114814Z.json`
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_cycle_fixture_20260224T114814Z.json`
- `docs/etl/sprints/AI-OPS-189/evidence/just_parl_run_sanction_procedural_official_review_raw_packets_cycle_dry_run_20260224T114738Z.txt`
- `docs/etl/sprints/AI-OPS-189/evidence/just_parl_test_sanction_data_catalog_20260224T114746Z.txt`
- `docs/etl/sprints/AI-OPS-189/evidence/just_parl_sanction_data_catalog_pipeline_20260224T114750Z.txt`
- `docs/etl/sprints/AI-OPS-189/exports/sanction_procedural_official_review_raw_from_packets_20260224T114727Z.csv`
- `docs/etl/sprints/AI-OPS-189/exports/sanction_procedural_official_review_raw_from_packets_via_just_20260224T114738Z.csv`
- `docs/etl/sprints/AI-OPS-189/exports/sanction_procedural_official_review_raw_from_packets_fixture_20260224T114814Z.csv`
