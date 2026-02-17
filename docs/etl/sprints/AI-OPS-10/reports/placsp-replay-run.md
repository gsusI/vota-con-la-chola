# AI-OPS-10 T13 PLACSP Replay/From-File Run

Date:
- `2026-02-17`

Objective:
- Execute `from-file` and `replay` rows for `placsp_autonomico` and `placsp_sindicacion`, capture normalized snapshots, and compute parity summary.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/reports/placsp-strict-run.md`
- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
- `scripts/run_source_probe_matrix.sh`

## Replay fixture preparation

Replay inputs were materialized at matrix-expected paths:
- `docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/placsp_autonomico/placsp_autonomico_replay_20260217.xml`
- `docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/placsp_sindicacion/placsp_sindicacion_replay_20260217.xml`

## Execution notes

- Initial parallel attempt caused SQLite contention (`database is locked`).
- All four rows were rerun serially; final artifacts below are from the successful serial pass.

## Output contract artifacts

Logs:
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay-logs/`

SQL snapshots:
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay-sql/`

Report:
- `docs/etl/sprints/AI-OPS-10/reports/placsp-replay-run.md`

## Parity summary

Columns:
- `source_id`
- `mode`
- `run_records_loaded`
- `exit_code`
- `run_status`

1. `placsp_autonomico`
- `source_id=placsp_autonomico | mode=strict-network | run_records_loaded=0 | exit_code=1 | run_status=error`
- `source_id=placsp_autonomico | mode=from-file | run_records_loaded=2 | exit_code=0 | run_status=ok`
- `source_id=placsp_autonomico | mode=replay | run_records_loaded=2 | exit_code=0 | run_status=ok`
- replay parity (`from-file` vs `replay`): `MATCH` (`2 == 2`)

2. `placsp_sindicacion`
- `source_id=placsp_sindicacion | mode=strict-network | run_records_loaded=0 | exit_code=1 | run_status=error`
- `source_id=placsp_sindicacion | mode=from-file | run_records_loaded=3 | exit_code=0 | run_status=ok`
- `source_id=placsp_sindicacion | mode=replay | run_records_loaded=3 | exit_code=0 | run_status=ok`
- replay parity (`from-file` vs `replay`): `MATCH` (`3 == 3`)

## Failure signatures

Strict failures are inherited from T12 and unchanged:
- `Error: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self signed certificate in certificate chain (_ssl.c:1129)>`

Replay/from-file final pass:
- no stderr failure signature (all four rows exit `0` in final serial execution).

## Snapshot references

- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql/placsp_autonomico__strict-network_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql/placsp_sindicacion__strict-network_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay-sql/placsp_autonomico__from-file_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay-sql/placsp_autonomico__replay_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay-sql/placsp_sindicacion__from-file_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay-sql/placsp_sindicacion__replay_run_snapshot.csv`
