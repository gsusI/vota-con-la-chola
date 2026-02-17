# AI-OPS-07 BOE Connector Implementation

Date: 2026-02-16  
Repository: `REPO_ROOT/vota-con-la-chola`

## Objective

Implement minimal BOE legal ingest connector for baseline legal/electoral corroboration with:
- deterministic `source_record_id`,
- idempotent ingest behavior,
- traceability through `source_records`, `run_fetches`, `raw_fetches`, `ingestion_runs`.

## Code Changes

1. Config + source registration
- `etl/politicos_es/config.py`
  - Added source `boe_api_legal` (`default_url=https://www.boe.es/rss/boe.php`, `format=xml`, `fallback_file=etl/data/raw/samples/boe_api_legal_sample.xml`, `min_records_loaded_strict=5`).
- `etl/politicos_es/connectors/__init__.py`
  - Exported `BoeApiLegalConnector`.
- `etl/politicos_es/registry.py`
  - Registered `BoeApiLegalConnector()` in `get_connectors()`.

2. New connector
- `etl/politicos_es/connectors/boe_legal.py`
  - New `BoeApiLegalConnector` (`ingest_mode = "source_records_only"`).
  - Parses BOE RSS (`<item>` rows), canonicalizes URLs, extracts BOE reference code (`BOE-*`), parses publication date.
  - Builds deterministic `source_record_id`:
    - preferred: `boe_ref:<BOE-...>`
    - fallback: URL/title SHA256-based deterministic IDs.
  - Supports `--from-file` (single XML/JSON) and directory mode (`*.xml`).
  - Network contract-drift guard:
    - HTML payload or invalid RSS raises explicit error including `payload_sig=<sha256>`.
    - if not `--strict-network`, ingest falls back non-fatally to sample payload with reason preserved in run note/message.

3. Sample + tests
- Added sample payload:
  - `etl/data/raw/samples/boe_api_legal_sample.xml`
- Added focused tests:
  - `tests/test_boe_connector.py`
    - parser stability / deterministic `source_record_id`
    - source-record ingest idempotence
- Existing global sample e2e suite (`tests/test_samples_e2e`) now includes `boe_api_legal` via registry.

## Deterministic `source_record_id` Evidence

Command:
```bash
python3 - <<'PY'
from pathlib import Path
from etl.politicos_es.connectors.boe_legal import parse_boe_rss_items
payload = Path('etl/data/raw/samples/boe_api_legal_sample.xml').read_bytes()
rows = parse_boe_rss_items(payload, feed_url='https://www.boe.es/rss/boe.php', content_type='text/xml')
for r in rows:
    print(r['source_record_id'], '|', r.get('boe_ref'), '|', r.get('source_url'))
PY
```

Output:
```text
boe_ref:BOE-A-2026-3482 | BOE-A-2026-3482 | https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-3482
boe_ref:BOE-A-2026-3499 | BOE-A-2026-3499 | https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-3499
boe_ref:BOE-S-2026-41 | BOE-S-2026-41 | https://www.boe.es/boe/dias/2026/02/16/
```

## Test Results

Command:
```bash
python3 -m unittest tests.test_boe_connector
```

Output:
```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.071s

OK
```

Command:
```bash
python3 -m unittest tests.test_samples_e2e
```

Output:
```text
.
----------------------------------------------------------------------
Ran 1 test in 0.685s

OK
```

## Ingest + Traceability Evidence

Command:
```bash
python3 scripts/ingestar_politicos_es.py ingest \
  --db etl/data/staging/politicos-es.db \
  --source boe_api_legal \
  --from-file etl/data/raw/samples/boe_api_legal_sample.xml \
  --snapshot-date 2026-02-16 \
  --strict-network --timeout 30
```

Output:
```text
boe_api_legal: 3/3 registros validos [from-file]
Total: 3/3 registros validos
```

Acceptance query command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, records_loaded FROM ingestion_runs WHERE source_id LIKE 'boe_%' ORDER BY run_id DESC LIMIT 10;"
```

Output:
```text
source_id      records_loaded
-------------  --------------
boe_api_legal  3
boe_api_legal  3
```

`source_records` idempotence evidence:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS source_records_total, COUNT(DISTINCT source_record_id) AS source_record_ids_distinct FROM source_records WHERE source_id='boe_api_legal';"
```

Output:
```text
source_records_total  source_record_ids_distinct
--------------------  --------------------------
3                     3
```

`run_fetches` / `raw_fetches` evidence:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT run_id, source_url, bytes FROM run_fetches WHERE source_id='boe_api_legal' ORDER BY run_id DESC LIMIT 2;"
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS raw_fetches_rows, COUNT(DISTINCT content_sha256) AS distinct_payloads FROM raw_fetches WHERE source_id='boe_api_legal';"
```

Output:
```text
run_id  source_url                                                                                                                                                             bytes
------  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------  -----
174     file://REPO_ROOT/vota-con-la-chola/etl/data/raw/samples/boe_api_legal_sample.xml  1946
173     file://REPO_ROOT/vota-con-la-chola/etl/data/raw/samples/boe_api_legal_sample.xml  2515

raw_fetches_rows  distinct_payloads
----------------  -----------------
2                 2
```

## Upstream Contract Drift (Non-Fatal) Evidence

Command (forcing HTML contract drift endpoint on purpose, without `--strict-network`):
```bash
python3 scripts/ingestar_politicos_es.py ingest \
  --db etl/data/staging/politicos-es.db \
  --source boe_api_legal \
  --url https://www.boe.es/datosabiertos/api/api.php \
  --snapshot-date 2026-02-16 \
  --timeout 30
```

Output:
```text
boe_api_legal: 3/3 registros validos [network-error-fallback: RuntimeError: Respuesta HTML inesperada para BOE RSS (payload_sig=600ef6f6bf651f9e9555ae80f03ad205ddbe3f97d3419e9b5f541946a8e05c96)]
Total: 3/3 registros validos
```

Latest run message:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT run_id, status, records_seen, records_loaded, message FROM ingestion_runs WHERE source_id='boe_api_legal' ORDER BY run_id DESC LIMIT 1;"
```

Output:
```text
run_id  status  records_seen  records_loaded  message
------  ------  ------------  --------------  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
174     ok      3             3               Ingesta completada: 3/3 registros validos (network-error-fallback: RuntimeError: Respuesta HTML inesperada para BOE RSS (payload_sig=600ef6f6bf651f9e9555ae80f03ad205ddbe3f97d3419e9b5f541946a8e05c96))
```

## FK Integrity Check

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Output:
```text
fk_violations
-------------
0
```

## Result

- BOE legal connector slice (`boe_api_legal`) is implemented and wired to existing ingest path.
- Deterministic `source_record_id` is enforced and tested.
- Idempotence validated in focused tests and in global sample e2e.
- Traceability persistence is verified across `source_records`, `run_fetches`, `raw_fetches`, and `ingestion_runs`.
- Upstream BOE contract drift now degrades gracefully (non-fatal fallback) with explicit reason and `payload_sig` for auditability.
