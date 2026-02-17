# AI-OPS-09 BDNS Connector Implementation

Date: 2026-02-17

## Scope

Implemented a minimal, reproducible BDNS/SNPSAP ingest slice with deterministic `source_record_id`, traceable subsidy fields (`beneficiario`, `importe`) and sample-backed tests.

## Code changes

- New connector module:
  - `etl/politicos_es/connectors/bdns_subsidies.py`
- Registry wiring:
  - `etl/politicos_es/connectors/__init__.py`
  - `etl/politicos_es/registry.py`
- Samples:
  - `etl/data/raw/samples/bdns_api_subvenciones_sample.json`
  - `etl/data/raw/samples/bdns_autonomico_sample.json`
- Tests:
  - `tests/test_bdns_connector.py`

## Contract behavior

### 1) Deterministic source_record_id

`source_record_id` is computed with deterministic fallback order:

1. `concesion:<normalized_concesion_id>`
2. `conv:<normalized_convocatoria_id>:benid:<normalized_beneficiario_id>`
3. `conv:<normalized_convocatoria_id>:ben:<normalized_beneficiario>`
4. `conv:<normalized_convocatoria_id>:amount:<importe>:date:<published_date>`
5. `url:<sha24(source_url)>`
6. `row:<sha24(raw_row_stable_json)>`

This guarantees idempotent upsert behavior on `(source_id, source_record_id)`.

### 2) Canonical subsidy fields parsed

The parser extracts and preserves these canonical fields per record:

- `convocatoria_id`
- `concesion_id`
- `organo_convocante`
- `beneficiario`
- `beneficiario_id`
- `importe_eur`
- `currency`
- `published_at_iso`
- `source_url`

It also stores `raw_row` in payload for traceability.

### 3) strict-network and fallback behavior

- With `--strict-network`: network/parser errors fail fast.
- Without `--strict-network`: connector remains non-fatal and falls back to sample payload configured in `fallback_file`.
- Drift diagnostics include payload signature (`payload_sig`) in parse/network failures.

## Beneficiary identity fallback (escalation rule)

If beneficiary identity is unstable or missing:
- keep nullable normalized fields (`beneficiario_id` can be `NULL`/empty),
- keep `beneficiario` text when present,
- preserve full `raw_row` payload,
- keep deterministic `source_record_id` through non-beneficiary fallback tiers.

## Validation commands and results

### Focused BDNS tests

Command:
```bash
python3 -m unittest discover -s tests -p 'test*bdns*py'
```

Output:
```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.068s

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
Ran 1 test in 0.483s

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
    db_path = Path(td) / 'bdns-evidence.db'
    raw_dir = Path(td) / 'raw'
    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        connectors = get_connectors()
        for source_id in ('bdns_api_subvenciones', 'bdns_autonomico'):
            sample = Path('etl/data/raw/samples') / f'{source_id}_sample.json'
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
        for row in conn.execute("SELECT source_id, COUNT(*) AS c FROM source_records WHERE source_id LIKE 'bdns_%' GROUP BY source_id ORDER BY source_id"):
            print(f"{row['source_id']}={row['c']}")
    finally:
        conn.close()
PY
```

Output:
```text
bdns_api_subvenciones=3
bdns_autonomico=2
```

## Escalation status

No escalation required in this slice.
