# AI-OPS-190 - Packet readiness/progress lane for official procedural review

## Objetivo
Cerrar la brecha operativa entre “paquetes exportados” y “paquetes realmente cargables” con un diagnóstico reproducible por fuente antes de ejecutar el ciclo `raw -> prepare -> apply`.

## Entregado
- `scripts/report_sanction_procedural_official_review_raw_packets_progress.py`
  - valida paquetes esperados desde la cola KPI (`build_raw_packets_from_gap_queue`) contra un `--packets-dir`;
  - clasifica cada paquete en estados operativos deterministas:
    - `missing_packet_file`
    - `invalid_headers`
    - `empty_packet`
    - `multiple_rows`
    - `invalid_row`
    - `ready`
  - reporta por fuente:
    - `missing_required_fields`
    - `row_reject_reasons`/`row_reject_priority`
    - `ready_for_transform`
  - soporta gates opcionales:
    - `--strict-actionable` (falla si no hay paquetes esperados),
    - `--strict-ready` (falla si no están todos `ready`).
- `justfile`
  - variables nuevas `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_*`;
  - lane nueva:
    - `parl-report-sanction-procedural-official-review-raw-packets-progress`;
  - integración de la lane en `parl-sanction-data-catalog-pipeline`.
- Tests
  - `tests/test_report_sanction_procedural_official_review_raw_packets_progress.py` (`Ran 3`).
  - `parl-test-sanction-data-catalog` sube a `Ran 50`.

## Resultado de corrida
- Staging (`period=2026-02-12/year`, paquetes `AI-OPS-188/latest`):
  - `status=degraded`
  - `packets_expected_total=4`
  - `packets_found_total=4`
  - `packets_ready_total=0`
  - `packets_status_counts={invalid_row:4}`
  - rechazo homogéneo por paquete: `missing_required_fields` en evidencia/contadores + `row_reject_reasons=invalid_numeric|missing_required_metadata`.
- Fixture contractual (`AI-OPS-189` packet fixture, `--strict-ready`):
  - `status=ok`
  - `packets_expected_total=4`
  - `packets_ready_total=4`
  - `all_expected_packets_ready=true`
  - gate `strict-ready` pasa (`exit=0`).
- Integración:
  - `just parl-test-sanction-data-catalog` -> `Ran 50`, `OK`.
  - `just parl-sanction-data-catalog-pipeline` -> `OK` con lane AI-OPS-190 incluida.

## Conclusión operativa
`Scenario A` ahora tiene un checkpoint explícito de “readiness real” de captura oficial por fuente antes del ciclo de carga. Esto evita iteraciones ciegas y da lista accionable exacta de campos faltantes por paquete.

## Evidencia
- `docs/etl/sprints/AI-OPS-190/evidence/sanction_procedural_official_review_raw_packets_progress_latest.json`
- `docs/etl/sprints/AI-OPS-190/exports/sanction_procedural_official_review_raw_packets_progress_latest.csv`
- `docs/etl/sprints/AI-OPS-190/evidence/sanction_procedural_official_review_raw_packets_progress_latest_period_20260224T115621Z.json`
- `docs/etl/sprints/AI-OPS-190/exports/sanction_procedural_official_review_raw_packets_progress_latest_period_20260224T115621Z.csv`
- `docs/etl/sprints/AI-OPS-190/evidence/sanction_procedural_official_review_raw_packets_progress_fixture_20260224T115600Z.json`
- `docs/etl/sprints/AI-OPS-190/exports/sanction_procedural_official_review_raw_packets_progress_fixture_20260224T115600Z.csv`
- `docs/etl/sprints/AI-OPS-190/evidence/just_parl_test_sanction_data_catalog_20260224T115848Z.txt`
- `docs/etl/sprints/AI-OPS-190/evidence/just_parl_report_sanction_procedural_official_review_raw_packets_progress_20260224T115636Z.txt`
- `docs/etl/sprints/AI-OPS-190/evidence/just_parl_sanction_data_catalog_pipeline_20260224T115636Z.txt`
