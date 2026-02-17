# AEMET Contract Hardening (T6)

Date:
- `2026-02-17`

Objective:
- Make `aemet_opendata_series` strict/replay behavior deterministic and add explicit blocker classification (`auth`, `contract`, `network`) for strict-mode failures.

## Root cause observed (AI-OPS-09)

Evidence showed two drift classes:

1. Strict-network endpoint failures:
- strict runs failed with `HTTP Error 404: No Encontrado` on current URL path.
- this is a contract/upstream issue, not a DB parity issue.

2. Replay fixture contract gaps:
- replay paths were missing expected fixture files in some packets (`FileNotFoundError`), and replay shape was not always guaranteed to be parser-compatible.
- parity rows stayed at `run_records_loaded=0` because fixture contract was broken.

Representative evidence:
- `docs/etl/sprints/AI-OPS-09/evidence/aemet-ingest-logs/sql/station_3195_tmed__strict-network_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/aemet-ingest-logs/sql/station_3195_tmed__replay_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/aemet-ingest-logs/station_3195_tmed__strict-network.stderr.log`
- `docs/etl/sprints/AI-OPS-09/evidence/aemet-ingest-logs/station_3195_tmed__replay.stderr.log`

## Implementation changes

1. Unified strict/replay parse contract:
- `etl/politicos_es/connectors/aemet_indicators.py`
- `parse_aemet_records` now accepts:
  - raw AEMET payloads (`series`/`datos`)
  - serialized replay containers with `records` (same shape emitted by strict/from-file extraction output)

2. Explicit wrong-fixture guardrail:
- parser now fails fast on legacy run snapshot payloads (`metric,value`) with a targeted contract error.

3. Blocker classification metadata:
- strict-mode failures now raise normalized signatures:
  - `aemet_blocker=auth; ...`
  - `aemet_blocker=contract; ...`
  - `aemet_blocker=network; ...`
- non-strict fallback notes now include classified prefixes (`auth-error-fallback`, `contract-error-fallback`, `network-error-fallback`).

4. Config contract note:
- `etl/politicos_es/config.py`
- clarified `aemet_opendata_series` `fallback_file` must remain raw AEMET payload shape, not run snapshot CSV.

## Test coverage updates

- `tests/test_aemet_connector.py`
  - added replay-container compatibility test.
  - added explicit `metric,value` rejection test.
  - added strict 404 classification test (`aemet_blocker=contract`).
- `tests/test_samples_e2e.py`
  - added deterministic replay ingest coverage for one stable series:
    - `station_id=3195`
    - `variable=tmed`
    - expected `source_record_id=station:3195:var:tmed`

## Exact failure signatures (now normalized)

- strict contract example:
  - `aemet_blocker=contract; error_type=HTTPError; detail=HTTP Error 404: No Encontrado`
- strict auth example:
  - `aemet_blocker=auth; error_type=RuntimeError; detail=AEMET_API_KEY no definido: ...`
- replay fixture gap example:
  - `aemet_blocker=contract; error_type=FileNotFoundError; detail=[Errno 2] No such file or directory ...`

## Validation executed

Commands:
```bash
python3 -m unittest tests.test_aemet_connector
python3 -m unittest tests.test_samples_e2e
```

Result:
- PASS (`7` AEMET connector tests, `4` samples E2E tests)

## Residual blocker notes

- Upstream token/quota and endpoint contract may still block strict-network runs in this environment.
- This packet resolves deterministic replay parsing and blocker classification; it does not claim strict upstream availability.

