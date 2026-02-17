# AI-OPS-10 T15 BDNS Replay/From-File Run

Date:
- `2026-02-17`

Objective:
- Execute BDNS `from-file` and `replay` rows, capture normalized snapshots, compare against strict runs, and publish per-source parity summary.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/reports/bdns-strict-run.md`
- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
- `scripts/run_source_probe_matrix.sh`

## Replay fixture preparation

Replay input fixtures were created at matrix-expected paths:
- `docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/bdns_autonomico/bdns_autonomico_replay_20260217.json`
- `docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/bdns_api_subvenciones/bdns_api_subvenciones_replay_20260217.json`

## Output contract artifacts

Logs:
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay-logs/`

SQL snapshots:
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay-sql/`

Report:
- `docs/etl/sprints/AI-OPS-10/reports/bdns-replay-run.md`

## Per-source parity summary

Columns:
- `source_id`
- `mode`
- `run_records_loaded`
- `exit_code`
- `run_status`
- `parity`

1. `bdns_autonomico`
- `source_id=bdns_autonomico | mode=strict-network | run_records_loaded=0 | exit_code=1 | run_status=error`
- `source_id=bdns_autonomico | mode=from-file | run_records_loaded=2 | exit_code=0 | run_status=ok`
- `source_id=bdns_autonomico | mode=replay | run_records_loaded=2 | exit_code=0 | run_status=ok`
- `parity(from-file vs replay)=MATCH` (`2 == 2`)

2. `bdns_api_subvenciones`
- `source_id=bdns_api_subvenciones | mode=strict-network | run_records_loaded=0 | exit_code=1 | run_status=error`
- `source_id=bdns_api_subvenciones | mode=from-file | run_records_loaded=3 | exit_code=0 | run_status=ok`
- `source_id=bdns_api_subvenciones | mode=replay | run_records_loaded=3 | exit_code=0 | run_status=ok`
- `parity(from-file vs replay)=MATCH` (`3 == 3`)

## Failure signatures

Strict-mode blocker inherited from T14:
- `Error: Respuesta HTML inesperada para BDNS feed (payload_sig=0401a40b059385b8a4d3e2fd933fe16213e22dd72df2f2fe2cdbd2872114c2fa)`

Replay/from-file final pass:
- no stderr failure signatures (all four rows completed with `exit_code=0`).

## Snapshot references

Strict:
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql/bdns_autonomico__strict-network_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql/bdns_api_subvenciones__strict-network_run_snapshot.csv`

From-file + replay:
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay-sql/bdns_autonomico__from-file_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay-sql/bdns_autonomico__replay_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay-sql/bdns_api_subvenciones__from-file_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay-sql/bdns_api_subvenciones__replay_run_snapshot.csv`
