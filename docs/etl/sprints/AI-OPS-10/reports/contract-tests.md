# AI-OPS-10 T9 Contract Tests

Date: 2026-02-17
Sprint: `docs/etl/sprints/AI-OPS-10/sprint-ai-agents.md` (Task 9)

## Where We Are Now

- Added focused tracker contract coverage in `tests/test_tracker_contract_parity.py`.
- Existing tracker and sample E2E coverage remains active in:
  - `tests/test_e2e_tracker_status_tracker.py`
  - `tests/test_samples_e2e.py`

## What Was Added

1. Replay snapshot normalization contract:
- Asserts canonical `run_snapshot` field set/order via `NORMALIZED_RUN_SNAPSHOT_FIELDS`.
- Verifies replay row inference for `source_id`, `snapshot_date`, and `entity_id`.

2. Source hardening regression checks (fallback/sample path):
- Verifies `from_file` extraction contract for:
  - `eurostat_sdmx`
  - `bde_series_api`
  - `aemet_opendata_series`
- Confirms parseable serialized payload envelope (`source`, `records`) and stable required fields.

3. PLACSP/BDNS artifact schema expectations:
- Verifies `from_file` extraction envelope/fields for:
  - `placsp_sindicacion`
  - `placsp_autonomico`
  - `bdns_api_subvenciones`
  - `bdns_autonomico`
- Confirms record-level required keys used by tracker/parity flows.

## Acceptance Evidence

Commands run:

```bash
python3 -m unittest discover -s tests -p 'test*tracker*py'
python3 -m unittest tests.test_samples_e2e
```

Results:

- `python3 -m unittest discover -s tests -p 'test*tracker*py'`
  - `Ran 23 tests in 0.162s`
  - `OK`
- `python3 -m unittest tests.test_samples_e2e`
  - `Ran 4 tests in 0.704s`
  - `OK`

## What Is Next

- Use this test packet as pre-flight gate before T10 handoff/runbook freeze.
- Keep these tests network-independent; expand only with deterministic sample fixtures.
