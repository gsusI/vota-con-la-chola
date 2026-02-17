# Indicator harmonization recompute (AI-OPS-09)

## Scope
Recompute canonical indicator series/points from Eurostat, BDE, and AEMET source records using `backfill-indicators`.

## Commands
1. Deterministic recompute command:
   - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-indicators --db etl/data/staging/politicos-es.db --source-ids eurostat_sdmx bde_series_api aemet_opendata_series"`
2. Full command output captured in:
   - `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/backfill-indicators.log`

## Before snapshot
### Totals
- `indicator_series`:
  - `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/before_indicator_series_total.csv`
  - `indicator_series_count`
  - `6`
- `indicator_points`:
  - `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/before_indicator_points_total.csv`
  - `18`

### Source-level traceability and null checks
- `before_series_traceability_by_source.csv`
  - columns: `source_id,series_count,source_url_null_count,source_record_pk_null_count,source_snapshot_date_null_count,unit_null_count`
  - all counts for `unit_null_count` and traceability nulls were `0` for `aemet_opendata_series`, `bde_series_api`, `eurostat_sdmx`.
- `before_points_null_rates.csv`
  - `total_points, value_null_count, value_text_null_count, both_null_count`
  - `18,0,18,0`
- `before_series_by_source_frequency.csv`
  - `aemet_opendata_series,D,2`
  - `bde_series_api,M,2`
  - `eurostat_sdmx,A,2`
- `before_points_sample.csv` (first rows included with `source_id`, `frequency`, `unit`, `value`/`value_text` provenance)

## Command output summary
```json
{
  "sources": ["eurostat_sdmx", "bde_series_api", "aemet_opendata_series"],
  "source_records_seen": 2400,
  "source_records_mapped": 2400,
  "source_records_skipped": 0,
  "indicator_series_upserted": 2400,
  "indicator_points_upserted": 37431,
  "indicator_points_deleted_stale": 0,
  "observation_records_upserted": 37431,
  "observation_records_deleted_stale": 0,
  "points_skipped_unparseable_date": 0,
  "skips": [],
  "indicator_series_total": 2400,
  "indicator_points_total": 37431,
  "indicator_observation_records_total": 37431,
  "indicator_series_with_provenance": 2400,
  "observation_records_with_provenance": 37431,
  "indicator_series_by_source": {
    "aemet_opendata_series": 2,
    "bde_series_api": 2,
    "eurostat_sdmx": 2396
  },
  "indicator_points_by_source": {
    "aemet_opendata_series": 6,
    "bde_series_api": 6,
    "eurostat_sdmx": 37419
  },
  "observation_records_by_source": {
    "aemet_opendata_series": 6,
    "bde_series_api": 6,
    "eurostat_sdmx": 37419
  }
}
```

## After snapshot
### Totals
- `indicator_series`:
  - `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/after_indicator_series_total.csv`
  - `2400`
- `indicator_points`:
  - `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/after_indicator_points_total.csv`
  - `37431`

### Source-level traceability and null checks
- `after_series_traceability_by_source.csv`
  - source_ids (`aemet_opendata_series`, `bde_series_api`, `eurostat_sdmx`) all with `source_url_null_count=0`, `source_record_pk_null_count=0`, `source_snapshot_date_null_count=0`.
- `after_series_unit_freq_nulls.csv`
  - no unit/frequency nulls for all three sources.
- `after_points_null_rates.csv`
  - `37431,0,37431,0` (`value_text` populated only when non-numeric, `value` populated in all rows).
- `after_series_by_source_frequency.csv`
  - `aemet_opendata_series,D,2,2`
  - `bde_series_api,M,2,2`
  - `eurostat_sdmx,A,2396,3`
  - (`distinct_units` shown for cross-check; units are explicit in canonical keys).
- `after_points_sample.csv` captures traceability (`source_id`, `frequency`, `unit`) for first rows.

## Compatibility / unit consistency check
- Audit query: check for repeated `series_code` with multiple `unit` or `frequency` values for each source.
- Result: no collisions detected in current snapshot (no rows returned).
- Therefore no silent incompatible-unit mixing found.

## Before/after delta
- `indicator_series`: `6 -> 2400` (+2394)
- `indicator_points`: `18 -> 37431` (+37413)
- `unit_text`/`frequency` nulls remain `0` and source provenance stayed complete.

## Outputs
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/backfill-indicators.log`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/before_indicator_series_total.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/after_indicator_series_total.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/before_indicator_points_total.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/after_indicator_points_total.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/before_series_traceability_by_source.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/after_series_traceability_by_source.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/before_series_unit_freq_nulls.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/after_series_unit_freq_nulls.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/before_points_null_rates.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/after_points_null_rates.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/before_series_by_source_frequency.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/after_series_by_source_frequency.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/before_points_sample.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/indicator-recompute-sql/after_points_sample.csv`
