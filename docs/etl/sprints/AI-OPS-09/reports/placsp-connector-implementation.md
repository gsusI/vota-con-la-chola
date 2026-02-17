# AI-OPS-09 PLACSP Connector Implementation

Date: 2026-02-17

## Scope

Implemented a minimal, reproducible PLACSP ingest slice for contracting records with deterministic `source_record_id`, traceable normalized fields, and sample-backed tests.

## Code changes

- New connector module:
  - `etl/politicos_es/connectors/placsp_contracts.py`
- Registry wiring:
  - `etl/politicos_es/connectors/__init__.py`
  - `etl/politicos_es/registry.py`
- Samples:
  - `etl/data/raw/samples/placsp_sindicacion_sample.xml`
  - `etl/data/raw/samples/placsp_autonomico_sample.xml`
- Tests:
  - `tests/test_placsp_connector.py`

## Contract behavior

### 1) Deterministic source_record_id

The connector computes stable `source_record_id` with deterministic precedence:

1. `expediente:<normalized_expediente>:<url_sha12>` (preferred)
2. `entry:<sha24(entry_id)>`
3. `url:<sha24(source_url)>`
4. `title:<sha24(title)>`

This keeps idempotent upserts stable on `(source_id, source_record_id)` across re-runs.

### 2) Normalized contracting fields

Each parsed entry keeps normalized contracting keys in `raw_payload` while preserving original content:

- `expediente`
- `organo_contratacion`
- `cpv` and `cpv_codes`
- `amount_eur` (+ `currency` when detected)
- `published_at_iso`
- traceability fields (`source_url`, `feed_url`, `entry_id`, `source_record_id`)

### 3) strict-network and fallback behavior

- With `--strict-network`: network/parser errors fail fast.
- Without `--strict-network`: ingest stays non-fatal and falls back to configured sample file.
- Fallback writes explicit note format:
  - `network-error-fallback: <ExceptionType>: <message>`
- Parser errors include payload signature (`payload_sig`) to aid upstream contract drift diagnosis.

## Validation commands and results

### Focused PLACSP tests

Command:
```bash
python3 -m unittest discover -s tests -p 'test*placsp*py'
```

Output:
```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.062s

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
    db_path = Path(td) / 'placsp-evidence.db'
    raw_dir = Path(td) / 'raw'
    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        connectors = get_connectors()
        for source_id in ('placsp_sindicacion', 'placsp_autonomico'):
            sample = Path('etl/data/raw/samples') / f'{source_id}_sample.xml'
            ingest_one_source(
                conn=conn,
                connector=connectors[source_id],
                raw_dir=raw_dir,
                timeout=5,
                from_file=sample,
                url_override=None,
                snapshot_date='2026-02-16',
                strict_network=True,
            )
        for row in conn.execute("SELECT source_id, COUNT(*) AS c FROM source_records WHERE source_id LIKE 'placsp_%' GROUP BY source_id ORDER BY source_id"):
            print(f"{row['source_id']}={row['c']}")
    finally:
        conn.close()
PY
```

Output:
```text
placsp_autonomico=2
placsp_sindicacion=3
```

## Escalation rule status

No escalation required in this slice. If upstream PLACSP feed contract drifts, parser remains non-fatal in non-strict mode and logs explicit failure signature for triage.
