# AI-OPS-09 - Indicator Harmonization Backfill (Eurostat/BDE/AEMET)

## Scope
- Harmonize connector `source_records` into canonical indicator tables:
  - `indicator_series`
  - `indicator_points`
  - `indicator_observation_records`
- Keep deterministic recompute semantics (`idempotent` reruns).
- Preserve provenance fields and snapshot granularity.

## Implementation
- Backfill module:
  - `etl/politicos_es/indicator_backfill.py`
  - function: `backfill_indicator_harmonization(...)`
- CLI command:
  - `python3 scripts/ingestar_politicos_es.py backfill-indicators --db <db>`
  - wired in `etl/politicos_es/cli.py`
- Focused tests:
  - `tests/test_indicator_backfill.py`

## Mapping Contract
- Input source IDs:
  - `eurostat_sdmx`
  - `bde_series_api`
  - `aemet_opendata_series`
- Series harmonization:
  - deterministic `canonical_key` includes `source_id`, `series_code`, `frequency`, `unit`, and version token.
  - version token uses `metadata_version` when available; otherwise `snapshot` fallback.
- Point harmonization:
  - `period` normalized to ISO date (`YYYY-MM-DD`) by frequency-safe rules.
  - if a period cannot be reconciled safely, point is skipped (`no invented date`).
- Provenance:
  - series: `source_id`, `source_url`, `source_record_pk`, `source_snapshot_date`, `raw_payload`
  - observations: same source keys + `methodology_version` + point-level `raw_payload`
- Frequency safety rule:
  - conflicting frequencies are stored as separate series variants (no forced merge).

## Commands and Outputs

### 1) Focused tests
Command:
```bash
python3 -m unittest discover -s tests -p 'test*indicator*backfill*py'
```
Output:
```text
..
----------------------------------------------------------------------
Ran 2 tests in 0.206s

OK
```

### 2) Sample ingest for the three indicator sources (staging DB)
Commands:
```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source eurostat_sdmx --from-file etl/data/raw/samples/eurostat_sdmx_sample.json --snapshot-date 2026-02-16 --strict-network
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bde_series_api --from-file etl/data/raw/samples/bde_series_api_sample.json --snapshot-date 2026-02-16 --strict-network
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source aemet_opendata_series --from-file etl/data/raw/samples/aemet_opendata_series_sample.json --snapshot-date 2026-02-16 --strict-network
```
Output:
```text
eurostat_sdmx: 2/2 registros validos [from-file]
Total: 2/2 registros validos
bde_series_api: 2/2 registros validos [from-file]
Total: 2/2 registros validos
aemet_opendata_series: 2/2 registros validos [from-file]
Total: 2/2 registros validos
```

### 3) Indicator harmonization backfill (run 1)
Command:
```bash
python3 scripts/ingestar_politicos_es.py backfill-indicators --db etl/data/staging/politicos-es.db
```
Output:
```json
{
  "source_records_seen": 6,
  "source_records_mapped": 6,
  "source_records_skipped": 0,
  "indicator_series_upserted": 6,
  "indicator_points_upserted": 18,
  "indicator_observation_records_total": 18,
  "indicator_series_total": 6,
  "indicator_points_total": 18,
  "indicator_series_with_provenance": 6,
  "observation_records_with_provenance": 18,
  "indicator_series_by_source": {
    "aemet_opendata_series": 2,
    "bde_series_api": 2,
    "eurostat_sdmx": 2
  }
}
```

### 4) Idempotent recompute (run 2)
Command:
```bash
python3 scripts/ingestar_politicos_es.py backfill-indicators --db etl/data/staging/politicos-es.db
```
Output (key fields):
```json
{
  "source_records_seen": 6,
  "source_records_mapped": 6,
  "indicator_series_total": 6,
  "indicator_points_total": 18,
  "indicator_observation_records_total": 18
}
```
Result: totals remain stable across rerun (`idempotent`).

### 5) Acceptance queries
Commands:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM indicator_series;"
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM indicator_points;"
```
Outputs:
```text
6
18
```

### 6) Provenance + integrity checks
Commands:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS provenance_series FROM indicator_series WHERE source_id IN ('eurostat_sdmx','bde_series_api','aemet_opendata_series') AND source_url IS NOT NULL AND trim(source_url)<>'' AND source_record_pk IS NOT NULL AND source_snapshot_date IS NOT NULL AND trim(source_snapshot_date)<>'';"
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS provenance_obs FROM indicator_observation_records WHERE source_id IN ('eurostat_sdmx','bde_series_api','aemet_opendata_series') AND source_record_id IS NOT NULL AND trim(source_record_id)<>'' AND source_url IS NOT NULL AND trim(source_url)<>'' AND source_snapshot_date IS NOT NULL AND trim(source_snapshot_date)<>'' AND methodology_version IS NOT NULL AND trim(methodology_version)<>'';"
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```
Outputs:
```text
6
18
0
```

## Limits / Safety
- If frequency/period cannot be reconciled safely, points are skipped instead of inventing dates.
- Conflicting frequency variants are preserved as distinct series versions.
