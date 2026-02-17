# Eurostat Contract Hardening (T4)

Date:
- `2026-02-17`

Objective:
- Harden `eurostat_sdmx` strict/from-file/replay contract so replay fixtures are parser-compatible with strict payload assumptions and parity checks are deterministic.

## Root cause observed

AI-OPS-09 evidence showed replay drift was contract-shape related, not DB idempotence:
- strict run parsed JSON-stat and loaded records.
- replay/from-file paths pointed to files containing legacy `metric,value` run snapshot rows (CSV content with `.json` extension), which are not Eurostat payloads.
- result: parse failure (`JSON invalido para Eurostat`) and `run_records_loaded=0`.

Representative evidence:
- `docs/etl/sprints/AI-OPS-09/evidence/eurostat-ingest-logs/sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__strict-network_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/eurostat-ingest-logs/sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__from-file_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/eurostat-ingest-logs/sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__replay_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/eurostat-ingest-logs/une_rt_a_freq_A_geo_ES_unit_PC_ACT__from-file.stderr.log`

## Implementation changes

1. Eurostat parser now supports both valid replay fixture families:
- JSON-stat payloads (strict contract).
- serialized replay container payloads (`{"records":[...]}`) produced by prior strict/from-file extraction output.

File:
- `etl/politicos_es/connectors/eurostat_indicators.py`

2. Replay container normalization:
- normalizes dimensions, labels, points, codelists, and `source_record_id`.
- keeps deterministic point sorting and dedupe behavior identical to strict parser output.

3. Explicit guardrail for wrong fixture class:
- if payload begins with `metric,value`, parser now raises a targeted contract error explaining run snapshot CSV was supplied instead of Eurostat payload.

4. Config contract note:
- `etl/politicos_es/config.py` now explicitly states `eurostat_sdmx` `fallback_file` must remain raw JSON-stat payload.

## Test coverage updates

- `tests/test_eurostat_connector.py`
  - added replay-container compatibility test.
  - added explicit rejection test for legacy `metric,value` snapshot payload.
- `tests/test_samples_e2e.py`
  - added end-to-end test that ingests from a serialized Eurostat replay container fixture.

## Validation executed

Commands:
```bash
python3 -m unittest tests.test_eurostat_connector
python3 -m unittest tests.test_samples_e2e
```

Result:
- PASS (`5` Eurostat connector tests, `2` samples E2E tests)

## Before/after parity behavior

Before:
- strict JSON-stat path succeeded.
- replay/from-file failed when fixture content drifted to `metric,value` snapshots.
- parity runs reported `run_records_loaded=0` on replay rows due parser contract mismatch.

After:
- strict path unchanged (JSON-stat still canonical).
- replay/from-file accepts deterministic serialized replay containers with `records`.
- invalid `metric,value` payloads fail fast with explicit contract error (clear blocker classification instead of ambiguous JSON decode failure).

