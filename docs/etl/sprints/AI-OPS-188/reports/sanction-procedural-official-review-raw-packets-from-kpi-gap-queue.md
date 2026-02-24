# AI-OPS-188 - Export `raw packets` por fuente desde cola KPI

## Objetivo
Operativizar `Scenario A` para backlog `missing_metric` sin trabajo manual de particionado: pasar de cola `fuente x KPI` a paquetes raw `1 fuente -> 1 CSV` listos para captura oficial y posterior carga por ciclo estricto.

## Entregado
- `scripts/export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue.py`
  - consume cola KPI (`build_kpi_gap_queue_report`) con filtro por estado (`--statuses`, default `missing_metric`).
  - reusa template raw oficial (`build_raw_template`) y emite un archivo CSV por `sanction_source_id`.
  - exporta resumen JSON con:
    - totales (`queue_rows_seen_total`, `sources_actionable_total`, `packets_emitted_total`)
    - checks (`packets_complete_for_actionable_sources`)
    - preview de KPIs faltantes por fuente.
  - soporta scope temporal, `--queue-limit`, `--include-ready`, y gate `--strict-actionable`.
- `justfile`
  - lane nuevo: `parl-export-sanction-procedural-official-review-raw-packets-from-kpi-gap-queue`.
  - variables nuevas: `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_*`.
  - integrado en `parl-sanction-data-catalog-pipeline`.
- Tests
  - `tests/test_export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue.py` (`Ran 3`).
  - `parl-test-sanction-data-catalog` sube a `Ran 44`.

## Resultado de corrida (20260224T113504Z)
- Staging directo (`period_date=2025-12-31`, `period_granularity=year`, `statuses=missing_metric`):
  - `status=ok` (lane), `queue_report_status=degraded` (backlog real pendiente).
  - `queue_rows_seen_total=12`
  - `sources_actionable_total=4`
  - `packets_emitted_total=4`
  - `sources_skipped_missing_template_total=0`
  - `rows_skipped_filtered_status_total=0`
  - `kpis_missing_total=3` por fuente:
    - `kpi:formal_annulment_rate`
    - `kpi:recurso_estimation_rate`
    - `kpi:resolution_delay_p90_days`
- Corrida via `just` (`20260224T113514Z`):
  - misma contabilidad (`12` pares -> `4` paquetes) y checks en verde.
- Integracion pipeline:
  - `just parl-sanction-data-catalog-pipeline` en verde con lane AI-OPS-188 incluido.
  - lane por defecto genero artefactos `..._latest` para `snapshot_date` (`2026-02-12`) manteniendo contrato reproducible.
- Tests:
  - `just parl-test-sanction-data-catalog` -> `Ran 44`, OK.

## Conclusion operativa
El backlog `missing_metric` ya no requiere preparar CSV manual por fuente: la cola KPI se convierte directamente en paquetes raw listos para captura y recarga por ciclo estricto.

## Evidencia
- `docs/etl/sprints/AI-OPS-188/evidence/sanction_procedural_official_review_raw_packets_20260224T113504Z.json`
- `docs/etl/sprints/AI-OPS-188/evidence/sanction_procedural_official_review_raw_packets_stdout_20260224T113504Z.txt`
- `docs/etl/sprints/AI-OPS-188/evidence/sanction_procedural_official_review_raw_packets_via_just_20260224T113514Z.json`
- `docs/etl/sprints/AI-OPS-188/evidence/just_parl_export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue_20260224T113514Z.txt`
- `docs/etl/sprints/AI-OPS-188/evidence/just_parl_test_sanction_data_catalog_20260224T113522Z.txt`
- `docs/etl/sprints/AI-OPS-188/evidence/just_parl_sanction_data_catalog_pipeline_20260224T113526Z.txt`
- `docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_20260224T113504Z/es-sanctions-contencioso-sentencias__2025-12-31__year.csv`
- `docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_20260224T113504Z/es-sanctions-defensor-pueblo-quejas__2025-12-31__year.csv`
- `docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_20260224T113504Z/es-sanctions-teac-resolutions__2025-12-31__year.csv`
- `docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_20260224T113504Z/es-sanctions-tear-resolutions__2025-12-31__year.csv`
- `docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_via_just_20260224T113514Z/es-sanctions-contencioso-sentencias__2025-12-31__year.csv`
- `docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_via_just_20260224T113514Z/es-sanctions-defensor-pueblo-quejas__2025-12-31__year.csv`
- `docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_via_just_20260224T113514Z/es-sanctions-teac-resolutions__2025-12-31__year.csv`
- `docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_via_just_20260224T113514Z/es-sanctions-tear-resolutions__2025-12-31__year.csv`
