# AI-OPS-10 T16 Eurostat Apply

Date:
- `2026-02-17`

Objective:
- Run `eurostat_sdmx` `strict-network`, `from-file`, and `replay` rows and capture deterministic counters for parity review.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
- `docs/etl/sprints/AI-OPS-10/reports/eurostat-contract-hardening.md`
- `scripts/run_source_probe_matrix.sh`

## Replay fixture

Prepared replay input:
- `docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/eurostat_sdmx/eurostat_sdmx_replay_20260217.json`

## Output contract artifacts

Logs:
- `docs/etl/sprints/AI-OPS-10/evidence/eurostat-logs/`

SQL snapshots:
- `docs/etl/sprints/AI-OPS-10/evidence/eurostat-sql/`

Report:
- `docs/etl/sprints/AI-OPS-10/reports/eurostat-apply.md`

## Result table

`source_id=eurostat_sdmx`

1. `mode=strict-network`
- `exit_code=0`
- `run_status=ok`
- `run_records_loaded=2394`
- `run_records_seen=2394`
- `run_id=239`

2. `mode=from-file`
- `exit_code=0`
- `run_status=ok`
- `run_records_loaded=2`
- `run_records_seen=2`
- `run_id=240`

3. `mode=replay`
- `exit_code=0`
- `run_status=ok`
- `run_records_loaded=2`
- `run_records_seen=2`
- `run_id=241`

Parity checks:
- `from-file` vs `replay` counters: `MATCH` (`run_records_loaded=2` both modes).
- `strict-network` vs `replay`: different input scope/signature (live URL vs fixture), so direct count equality is not required.

## Escalation rule check

T16 escalation condition:
- escalate if `strict-network` succeeds but `replay` is zero-loaded with identical input signature.

Observed:
- `strict-network` succeeded.
- `replay` is non-zero (`run_records_loaded=2`).

Decision:
- `NO_ESCALATION`.
