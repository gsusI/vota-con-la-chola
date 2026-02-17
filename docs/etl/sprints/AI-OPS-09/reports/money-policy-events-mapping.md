# AI-OPS-09 - Money -> `policy_events` Mapping (PLACSP + BDNS)

## Scope
- Add deterministic mapping/backfill from money ingest records into canonical action rows in `policy_events`.
- Families covered:
  - `placsp_*` -> canonical `source_id='placsp_contratacion'`
  - `bdns_*` -> canonical `source_id='bdns_subvenciones'`

## Implementation Summary
- Mapping logic implemented in `etl/politicos_es/policy_events.py` via `backfill_money_policy_events(...)`.
- CLI command added in `etl/politicos_es/cli.py`:
  - `backfill-policy-events-money`
- Canonical mapped sources registered in `etl/politicos_es/config.py`:
  - `placsp_contratacion`
  - `bdns_subvenciones`
- Focused tests added in `tests/test_policy_money_mapping.py`:
  - idempotence
  - traceability fields
  - ambiguous/low-confidence amount behavior (`NULL` instead of invented values)

## Deterministic Mapping Rules
- PLACSP source IDs: `placsp_sindicacion`, `placsp_autonomico`
  - instrument: `public_contracting`
  - `policy_event_id`: `money:placsp:<source_id>:<source_record_id>`
- BDNS source IDs: `bdns_api_subvenciones`, `bdns_autonomico`
  - instrument: `public_subsidy`
  - `policy_event_id`: `money:bdns:<source_id>:<source_record_id>`
- Required traceability persisted in `policy_events`:
  - `source_id`
  - `source_url`
  - `source_record_pk`
  - `source_snapshot_date`
  - `raw_payload`
- Ambiguity policy:
  - keep `event_date = NULL` when causal date is not reliable
  - keep nullable values (`amount_eur`, `currency`) when payload confidence is insufficient

## Evidence Commands and Outputs

### 1) Focused mapping tests
Command:
```bash
python3 -m unittest discover -s tests -p 'test*policy*money*py'
```
Output:
```text
..
----------------------------------------------------------------------
Ran 2 tests in 0.094s

OK
```

### 2) Backfill run (staging DB)
Command:
```bash
python3 scripts/ingestar_politicos_es.py backfill-policy-events-money --db etl/data/staging/politicos-es.db
```
Output:
```json
{
  "sources": [
    "placsp_sindicacion",
    "placsp_autonomico",
    "bdns_api_subvenciones",
    "bdns_autonomico"
  ],
  "source_records_seen": 6,
  "source_records_mapped": 6,
  "source_records_skipped": 0,
  "policy_events_upserted": 6,
  "skips": [],
  "policy_events_total": 6,
  "policy_events_with_source_url": 6,
  "policy_events_with_source_record_pk": 6,
  "policy_events_by_source": {
    "bdns_subvenciones": 3,
    "placsp_contratacion": 3
  }
}
```

### 3) Acceptance count (canonical money source IDs)
Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM policy_events WHERE source_id IN ('placsp_contratacion','bdns_subvenciones');"
```
Output:
```text
6
```

### 4) Traceability coverage check
Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS traceable_rows FROM policy_events WHERE source_id IN ('placsp_contratacion','bdns_subvenciones') AND source_url IS NOT NULL AND trim(source_url)<>'' AND source_record_pk IS NOT NULL AND source_snapshot_date IS NOT NULL AND trim(source_snapshot_date)<>'';"
```
Output:
```text
6
```

### 5) Idempotence check (re-run)
Command:
```bash
python3 scripts/ingestar_politicos_es.py backfill-policy-events-money --db etl/data/staging/politicos-es.db
```
Output:
```json
{
  "source_records_seen": 6,
  "source_records_mapped": 6,
  "policy_events_total": 6,
  "policy_events_by_source": {
    "bdns_subvenciones": 3,
    "placsp_contratacion": 3
  }
}
```
Result: total row count stays stable (`6`) after re-run.

### 6) FK safety
Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```
Output:
```text
0
```

## Notes / Risk Controls
- Mapping is intentionally minimal and deterministic; no inferred semantics are fabricated.
- Where payload confidence is ambiguous, nullable fields are preserved as `NULL` per escalation rule.
