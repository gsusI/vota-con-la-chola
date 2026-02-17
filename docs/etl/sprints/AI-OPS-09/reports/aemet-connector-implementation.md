# AI-OPS-09 AEMET Connector Implementation

Date: 2026-02-17

## Scope

Implemented deterministic AEMET confounder ingest for station-linked time series with explicit token handling, station metadata normalization, and source-level traceability.

## Code changes

- New connector module:
  - `etl/politicos_es/connectors/aemet_indicators.py`
- Registry wiring:
  - `etl/politicos_es/connectors/__init__.py`
  - `etl/politicos_es/registry.py`
- Stable sample fixture:
  - `etl/data/raw/samples/aemet_opendata_series_sample.json`
- Focused tests:
  - `tests/test_aemet_connector.py`

## Parsing and normalization contract

### 1) Station and time-series coverage

Connector: `AemetOpenDataSeriesConnector` (`source_id=aemet_opendata_series`), `ingest_mode=source_records_only`.

Per record, parser normalizes:

- station metadata:
  - `station_id`
  - `station_name`
  - `province`
  - `lat`, `lon`
  - `altitude_m`
- series fields:
  - `dataset_code`
  - `variable`
  - `series_code`
  - `frequency`
  - `unit`
  - `points` (`period`, `value`, `value_text`)
  - `points_count`
- traceability:
  - `source_url`
  - `feed_url`
  - `metadata_refs` (includes AEMET `metadatos` URL when present)

### 2) Deterministic source_record_id

`source_record_id` is stable per station+variable:

- `station:<station_id>:var:<variable>`

Fallback path uses deterministic hash of `series_dimensions` when station/variable is missing.

### 3) Token handling (explicit)

Token support is optional and explicit via environment variable:

- `AEMET_API_KEY`

Behavior:

1. If URL contains `{api_key}`, connector requires `AEMET_API_KEY` and substitutes it.
2. If `AEMET_API_KEY` exists and URL has no `api_key`, connector appends `api_key` query parameter.
3. If no token is provided, connector still runs with URL as-is (useful for sample/offline runs).

The connector also supports AEMET envelope responses where first payload points to a secondary `datos` URL.

### 4) Reproducibility / fallback policy

- With `--strict-network`: fail fast on token/quota/network/parser errors.
- Without `--strict-network`: fallback to sample (`fallback_file`) and keep run non-fatal.
- Errors include payload signature (`payload_sig`) for drift/quota diagnostics.

## Validation commands and results

### Focused AEMET tests

Command:
```bash
python3 -m unittest discover -s tests -p 'test*aemet*py'
```

Output:
```text
....
----------------------------------------------------------------------
Ran 4 tests in 0.060s

OK
```

### Global samples idempotence test

Command:
```bash
python3 -m unittest tests.test_samples_e2e
```

Output:
```text
.
----------------------------------------------------------------------
Ran 1 test in 0.517s

OK
```

### Report keyword check

Command:
```bash
rg -n "station|token|traceability" docs/etl/sprints/AI-OPS-09/reports/aemet-connector-implementation.md
```

Output:
```text
(matches include station metadata, token policy, and traceability sections)
```

## Escalation rule status

No blocker observed in this slice. If token/quota blocks reproducibility in live runs, the connector already supports explicit fallback and should keep tracker row honest (`PARTIAL` with blocker evidence + next command).
