# AI-OPS-09 Eurostat Connector Implementation

Date: 2026-02-17

## Scope

Implemented deterministic Eurostat ingestion for curated indicators via JSON-stat/SDMX JSON payloads, preserving traceable series metadata, dimension codelists, and unit information.

## Code changes

- New connector module:
  - `etl/politicos_es/connectors/eurostat_indicators.py`
- Registry wiring:
  - `etl/politicos_es/connectors/__init__.py`
  - `etl/politicos_es/registry.py`
- Stable sample fixture:
  - `etl/data/raw/samples/eurostat_sdmx_sample.json`
- Focused tests:
  - `tests/test_eurostat_connector.py`

## Parsing and normalization contract

### 1) Endpoint and payload contract

- Connector: `EurostatSdmxConnector` (`source_id=eurostat_sdmx`)
- Contracted payload type: JSON-stat style dataset (`id`, `size`, `dimension`, `value`).
- Ingest mode: `source_records_only` for deterministic traceability before later mapping into `indicator_series`/`indicator_points`.

### 2) Canonical series structures

For each parsed series the connector stores canonical fields in `raw_payload`:

- `dataset_code`
- `series_code`
- `frequency`
- `unit`
- `series_dimensions`
- `series_dimension_labels`
- `time_dimension`
- `points` (`period`, `period_label`, `value`, `value_text`)
- `dimension_codelists` (codes + labels per dimension)
- `metadata_version`

This keeps `dimension`, `unit`, and `series` traceability explicit and versioned.

### 3) Deterministic source_record_id

`source_record_id` is stable per series:

- `series:<sha24(series_code)>`

Fallback (if needed): hash of deterministic `series_dimensions` JSON.

Idempotent upsert remains guaranteed by `(source_id, source_record_id)`.

### 4) Drift and isolation behavior

- Parse/network failures include payload signature (`payload_sig`) in error messages.
- With `--strict-network`: connector fails fast.
- Without `--strict-network`: connector falls back to configured sample and keeps failure isolated under `source_id=eurostat_sdmx`.

## Validation commands and results

### Focused Eurostat tests

Command:
```bash
python3 -m unittest discover -s tests -p 'test*eurostat*py'
```

Output:
```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.073s

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
Ran 1 test in 0.574s

OK
```

### Repro ingest probe (temp DB)

Command:
```bash
python3 - <<'PY'
import tempfile
from pathlib import Path
from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.registry import get_connectors

with tempfile.TemporaryDirectory() as td:
    db_path = Path(td) / 'eurostat-evidence.db'
    raw_dir = Path(td) / 'raw'
    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        connector = get_connectors()['eurostat_sdmx']
        sample = Path('etl/data/raw/samples/eurostat_sdmx_sample.json')
        ingest_one_source(
            conn=conn,
            connector=connector,
            raw_dir=raw_dir,
            timeout=5,
            from_file=sample,
            url_override=None,
            snapshot_date='2026-02-16',
            strict_network=True,
        )
        c = conn.execute("SELECT COUNT(*) AS c FROM source_records WHERE source_id='eurostat_sdmx'").fetchone()['c']
        print('eurostat_source_records', c)
    finally:
        conn.close()
PY
```

Output:
```text
eurostat_source_records 2
```

## Escalation status

No escalation required for this slice. If the dataset contract drifts, failure is isolated by source and includes drift evidence via payload signature.
