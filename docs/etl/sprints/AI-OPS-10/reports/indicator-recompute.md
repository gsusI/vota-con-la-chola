# AI-OPS-10 T20 Indicator Recompute

Date:
- `2026-02-17`

Objective:
- Recompute indicator harmonization and canonical points after Eurostat/BDE/AEMET apply wave and capture drift deltas.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/reports/eurostat-apply.md`
- `docs/etl/sprints/AI-OPS-10/reports/bde-apply.md`
- `docs/etl/sprints/AI-OPS-10/reports/aemet-apply.md`
- `scripts/ingestar_politicos_es.py`
- `etl/data/staging/politicos-es.db`

## Recompute command

```bash
python3 scripts/ingestar_politicos_es.py backfill-indicators \
  --db etl/data/staging/politicos-es.db \
  --source-ids eurostat_sdmx bde_series_api aemet_opendata_series
```

Backfill log:
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/backfill-indicators.log`

Command result summary:
- `sources=["eurostat_sdmx","bde_series_api","aemet_opendata_series"]`
- `source_records_seen=2400`
- `source_records_mapped=2400`
- `source_records_skipped=0`
- `indicator_series_upserted=2400`
- `indicator_points_upserted=37431`
- `observation_records_upserted=37431`
- `indicator_series_total=2400`
- `indicator_points_total=37431`
- `indicator_observation_records_total=37431`

## Evidence packet

- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_totals.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_totals.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_series_by_source.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_series_by_source.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_points_by_source.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_points_by_source.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_observation_by_source.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_observation_by_source.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_series_traceability.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_series_traceability.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_points_null_rates.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_points_null_rates.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_observation_null_rates.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_observation_null_rates.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_series_by_source_frequency.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_series_by_source_frequency.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_points_sample.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_points_sample.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/before_fk_check.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql/after_fk_check.csv`

## Before/After summary

Totals:
- `indicator_series_total`: `2400 -> 2400` (`delta=0`)
- `indicator_points_total`: `37431 -> 37431` (`delta=0`)
- `indicator_observation_records_total`: `37431 -> 37431` (`delta=0`)

Source-level totals:
- `aemet_opendata_series`: `series 2 -> 2`, `points 6 -> 6`, `observations 6 -> 6`
- `bde_series_api`: `series 2 -> 2`, `points 6 -> 6`, `observations 6 -> 6`
- `eurostat_sdmx`: `series 2396 -> 2396`, `points 37419 -> 37419`, `observations 37419 -> 37419`

Null/traceability checks:
- `points value_null_count`: `0 -> 0`
- `points both_missing_count`: `0 -> 0`
- `observation unit_blank_count`: all sources `0 -> 0`
- `observation frequency_blank_count`: all sources `0 -> 0`
- `series with_source_record_pk`: unchanged and complete for all three sources
- `series with_source_url`: unchanged and complete for all three sources

Schema note:
- `unit`/`frequency` checks are taken from `indicator_observation_records` and `indicator_series` (not `indicator_points`) for compatibility with current schema.

## Integrity and escalation check

Integrity:
- `PRAGMA foreign_key_check`: `0 -> 0` violations.

T20 escalation condition:
- escalate if recompute yields negative integrity drift or unexplained total collapse.

Observed:
- no integrity drift,
- no collapse in `indicator_series_total`,
- no collapse in `indicator_points_total`,
- no collapse in `indicator_observation_records_total`.

Decision:
- `NO_ESCALATION`.
