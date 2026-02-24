# AI-OPS-184 — KPI completeness + period-scope status gate for official procedural review

## Objetivo
Endurecer `Scenario A` para que la lane oficial no se considere “sana” con cobertura parcial de KPIs ni con mezcla de periodos.

## Entregado
- `scripts/report_sanction_procedural_official_review_status.py`
  - añade scope opcional por periodo:
    - `--period-date`
    - `--period-granularity`
  - nuevo estado de cola por fuente:
    - `partial_kpi_coverage`
    - `next_action=ingest_missing_kpis_for_source_scope`
  - nueva contabilidad y checks de completitud KPI:
    - `official_review_kpis_expected_total`
    - `official_review_sources_with_all_kpis_total`
    - `official_review_sources_with_missing_kpis_total`
    - `official_review_missing_kpi_pairs_total`
    - `official_review_source_full_kpi_coverage_pct`
    - check `official_review_all_seeded_have_all_kpis`
  - `status=degraded` cuando haya fuentes seed sin cobertura KPI completa para el scope.
  - CSV de cola amplía columnas:
    - `kpis_expected_total`
    - `kpis_missing_total`
- `justfile`
  - lane `parl-report-sanction-procedural-official-review-status` acepta scope opcional vía env:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_STATUS_PERIOD_DATE`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_STATUS_PERIOD_GRANULARITY`
- Tests
  - `tests/test_report_sanction_procedural_official_review_status.py` sube a `Ran 6` con nuevos casos:
    - detección de `partial_kpi_coverage`
    - aislamiento por `period_date/period_granularity`.
  - `parl-test-sanction-data-catalog` sube a `Ran 32`.

## Resultado de corrida (20260224T110525Z)
- Staging real, scope `2025-12-31/year`:
  - `status=degraded`
  - `official_review_sources_expected_total=4`
  - `official_review_sources_with_metrics_total=0`
  - `official_review_sources_with_all_kpis_total=0`
  - `official_review_kpis_expected_total=3`
  - `official_review_missing_kpi_pairs_total=12`
  - cola con `kpis_missing_total=3` por fuente (`no_metrics`).
- Fixture contractual de cobertura parcial:
  - `status=degraded` (scope `2025-12-31/year`)
  - `official_review_sources_with_metrics_total=1`
  - `official_review_sources_with_all_kpis_total=0`
  - `official_review_kpis_covered_total=2`
  - `official_review_missing_kpi_pairs_total=10`
  - fuente `teac` en `partial_kpi_coverage` con `kpis_missing_total=1`.
- Tests:
  - `just parl-test-sanction-data-catalog` -> `Ran 32`, OK.

## Conclusión operativa
La lane oficial ahora distingue explícitamente “hay métricas” de “están completos todos los KPIs esperados en el periodo objetivo”. Esto reduce falsos positivos de progreso y mejora el gate antes de declarar cobertura cerrada.

## Evidencia
- `docs/etl/sprints/AI-OPS-184/evidence/sanction_procedural_official_review_status_period_2025_20260224T110525Z.json`
- `docs/etl/sprints/AI-OPS-184/evidence/sanction_procedural_official_review_status_period_2025_via_just_20260224T110525Z.json`
- `docs/etl/sprints/AI-OPS-184/evidence/sanction_procedural_official_review_status_partial_kpi_fixture_20260224T110525Z.json`
- `docs/etl/sprints/AI-OPS-184/exports/sanction_procedural_official_review_queue_period_2025_20260224T110525Z.csv`
- `docs/etl/sprints/AI-OPS-184/exports/sanction_procedural_official_review_queue_period_2025_via_just_20260224T110525Z.csv`
- `docs/etl/sprints/AI-OPS-184/evidence/just_parl_report_sanction_procedural_official_review_status_period_2025_20260224T110525Z.txt`
- `docs/etl/sprints/AI-OPS-184/evidence/just_parl_test_sanction_data_catalog_20260224T110525Z.txt`
