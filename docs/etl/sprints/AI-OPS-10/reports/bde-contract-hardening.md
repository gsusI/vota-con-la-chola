# BDE Contract Hardening (T5)

Date:
- `2026-02-17`

Objective:
- Unify strict/replay parsing and replay fixture behavior for `bde_series_api`, so deterministic parity checks are valid when replay fixtures are capture-compatible.

## Root cause observed (AI-OPS-09)

Two failure classes were mixed in prior evidence:

1. Strict-network reachability failures:
- `strict-network` rows failed with network/DNS errors in this environment.
- This blocks live baseline runs but is an upstream availability issue, not parser drift.

2. Replay fixture shape drift:
- replay inputs often contained placeholder JSON or non-series artifacts.
- parser expected BDE series payload (`results/items/data/series` with observations) and returned no parseable series.
- replay run counters stayed `0` because input contract was incompatible, not because DB writes were non-deterministic.

Representative evidence:
- `docs/etl/sprints/AI-OPS-09/reports/bde-apply-recompute.md`
- `docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/PARO_TASA_ES_M__replay_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/PARO_TASA_ES_M__replay.stderr.log`

## Implementation changes

1. Parser contract hardening:
- `etl/politicos_es/connectors/bde_series.py`
- Added support for serialized replay containers with `records` (the shape emitted by strict/from-file extraction output).
- Added explicit guard for wrong fixture class (`metric,value` run snapshot CSV payload).

2. Stable series parsing normalization:
- centralized BDE field extraction (`series_code`, `frequency`, `unit`, `label`, points).
- normalized replay-container records to canonical BDE record shape before dedupe/load.

3. Config contract note:
- `etl/politicos_es/config.py`
- clarified that `bde_series_api` `fallback_file` must remain raw BDE payload shape, not run snapshot CSV.

## Test coverage updates

- `tests/test_bde_connector.py`
  - added replay-container compatibility test.
  - added explicit rejection test for `metric,value` snapshot payloads.
- `tests/test_samples_e2e.py`
  - added deterministic replay ingest test for one stable series (`PARO.TASA.ES.M`) using serialized replay container fixture.
  - validates deterministic stable `source_record_id` (`series:parotasaesm`) and non-zero load path.

## Validation executed

Commands:
```bash
python3 -m unittest tests.test_bde_connector
python3 -m unittest tests.test_samples_e2e
```

Result:
- PASS (`5` BDE connector tests, `3` samples E2E tests)

## Residual blocker notes

- Live strict-network BDE runs may still fail in this environment when upstream endpoint resolution is unavailable.
- This packet resolves parser/fixture determinism only; it does not claim upstream network reliability.
- Operational rule remains: use capture-compatible replay fixtures (`records` container or raw BDE payload) for deterministic parity when strict is blocked.

