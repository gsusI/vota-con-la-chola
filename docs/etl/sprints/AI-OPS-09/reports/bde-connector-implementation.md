# AI-OPS-09 BDE Connector Implementation

Date: 2026-02-17

## Scope

Implemented deterministic Banco de Espana (BDE) series ingestion for curated confounder indicators with stable series IDs and traceable metadata.

## Code changes

- New connector module:
  - `etl/politicos_es/connectors/bde_series.py`
- Registry wiring:
  - `etl/politicos_es/connectors/__init__.py`
  - `etl/politicos_es/registry.py`
- Stable sample fixture:
  - `etl/data/raw/samples/bde_series_api_sample.json`
- Focused tests:
  - `tests/test_bde_connector.py`

## Parsing and normalization contract

### 1) API/feed contract

- Connector: `BdeSeriesApiConnector` (`source_id=bde_series_api`)
- Contracted payload: JSON with series metadata + points under `points`/`observations`/`data`.
- Ingest mode: `source_records_only` to preserve deterministic source traceability.

### 2) Canonical fields

Per parsed series, connector emits canonical payload fields:

- `series_code`
- `series_label`
- `frequency`
- `unit`
- `series_dimensions`
- `dataset_code`
- `metadata_version`
- `points` (`period`, `value`, `value_text`)
- `points_count`

### 3) Deterministic source_record_id

`source_record_id` is stable per series:

- `series:<normalized_series_code>`

Fallback path (if code is missing): hash of `series_dimensions`.

This ensures idempotent upsert behavior on `(source_id, source_record_id)`.

### 4) Endpoint drift/auth policy

- Parse/network errors include payload signature (`payload_sig`) in error message.
- If endpoint drifts, failure remains isolated by `source_id=bde_series_api`.
- If upstream requires non-reproducible auth/cookies, policy is to stop and document blocker explicitly (no silent bypass).

## Validation commands and results

### Focused BDE tests

Command:
```bash
python3 -m unittest discover -s tests -p 'test*bde*py'
```

Output:
```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.050s

OK
```

### Field presence check in report

Command:
```bash
rg -n "frequency|unit|series" docs/etl/sprints/AI-OPS-09/reports/bde-connector-implementation.md
```

Output:
```text
(matches include frequency/unit/series sections and field list)
```

## Escalation status

No blocker observed in this implementation slice.
