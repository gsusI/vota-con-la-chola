# Contract Schema Normalization (T2)

Date:
- `2026-02-17`

Objective:
- Normalize run snapshot artifacts to one canonical CSV schema so strict/from-file/replay parity checks are machine-comparable across source families.

## What changed

1. Shared canonical snapshot schema helper:
- `etl/politicos_es/run_snapshot_schema.py`
- Canonical fields (stable order):
  - `schema_version`
  - `source_id`
  - `mode`
  - `exit_code`
  - `run_records_loaded`
  - `snapshot_date`
  - `run_id`
  - `run_status`
  - `run_records_seen`
  - `before_records`
  - `after_records`
  - `delta_records`
  - `run_started_at`
  - `run_finished_at`
  - `source_url`
  - `command`
  - `message`
  - `source_record_id`
  - `entity_id`
- Supports both input families:
  - legacy `metric,value`
  - tabular one-row CSV

2. Tracker tool normalization mode:
- `scripts/e2e_tracker_status.py`
- Added CLI path to normalize any existing run snapshot file:
  - `--normalize-run-snapshot-in`
  - `--normalize-run-snapshot-out`
  - `--normalize-run-snapshot-legacy-out`
  - optional overrides: `source_id`, `mode`, `snapshot_date`

3. Politicos ETL export command:
- `etl/politicos_es/cli.py`
- New subcommand:
  - `export-run-snapshot`
- Writes canonical schema (`schema v2`) from `ingestion_runs` + `source_records` counts.
- Optional legacy output remains available via `--legacy-kv-out`.

4. Entrypoint compatibility:
- `scripts/ingestar_politicos_es.py` now forwards argv explicitly (`main(sys.argv[1:])`) so new subcommands behave deterministically in wrapper execution.

## Backward compatibility

- Existing legacy snapshots are still supported as input.
- Optional legacy output (`metric,value`) can still be produced.
- Existing tracker SQL status logic remains unchanged.

## Usage

Normalize legacy/tabular run snapshot file in place:
```bash
python3 scripts/e2e_tracker_status.py \
  --normalize-run-snapshot-in docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-sql/placsp_autonomico__strict-network_run_snapshot.csv \
  --normalize-run-snapshot-out docs/etl/sprints/AI-OPS-10/evidence/placsp_autonomico__strict-network_run_snapshot.v2.csv
```

Export canonical run snapshot directly from DB:
```bash
python3 scripts/ingestar_politicos_es.py export-run-snapshot \
  --db etl/data/staging/politicos-es.db \
  --source-id placsp_autonomico \
  --run-id 195 \
  --mode strict-network \
  --snapshot-date 2026-02-17 \
  --out docs/etl/sprints/AI-OPS-10/evidence/placsp_autonomico__strict-network_run_snapshot.v2.csv
```

## Validation executed

- Unit tests:
  - `python3 -m unittest tests.test_run_snapshot_schema tests.test_e2e_tracker_status_tracker`
- CLI smoke:
  - `python3 scripts/ingestar_politicos_es.py --help`
  - `python3 scripts/ingestar_politicos_es.py export-run-snapshot --help`
  - `python3 scripts/e2e_tracker_status.py --help`

Result:
- PASS (tests green and commands available)

## Notes for next packets (T3+)

- Replace ad-hoc `metric,value` writers in throughput scripts with either:
  - `scripts/ingestar_politicos_es.py export-run-snapshot`, or
  - `scripts/e2e_tracker_status.py --normalize-run-snapshot-*` on produced artifacts.
- Parity checks should consume canonical fields only (`source_id`, `mode`, `exit_code`, `run_records_loaded`, `snapshot_date`, `run_id`).
