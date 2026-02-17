# AI-OPS-10 T17 BDE Apply

Date:
- `2026-02-17`

Objective:
- Validate deterministic behavior for `bde_series_api` under `strict-network`, `from-file`, and `replay`.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
- `docs/etl/sprints/AI-OPS-10/reports/bde-contract-hardening.md`
- `scripts/run_source_probe_matrix.sh`

## Replay fixture

Prepared replay input:
- `docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/bde_series_api/bde_series_api_replay_20260217.json`

## Output contract artifacts

Logs:
- `docs/etl/sprints/AI-OPS-10/evidence/bde-logs/`

SQL snapshots:
- `docs/etl/sprints/AI-OPS-10/evidence/bde-sql/`

Report:
- `docs/etl/sprints/AI-OPS-10/reports/bde-apply.md`

## Result table (`source_id=bde_series_api`)

1. `mode=strict-network`
- `exit_code=1`
- `run_status=error`
- `run_records_loaded=0`
- `run_records_seen=0`
- `run_id=242`
- blocker signature:
  - `Error: <urlopen error [Errno 8] nodename nor servname provided, or not known>`

2. `mode=from-file`
- `exit_code=0`
- `run_status=ok`
- `run_records_loaded=2`
- `run_records_seen=2`
- `run_id=243`

3. `mode=replay`
- `exit_code=0`
- `run_status=ok`
- `run_records_loaded=2`
- `run_records_seen=2`
- `run_id=244`

Parity checks:
- `from-file` vs `replay`: `MATCH` (`run_records_loaded=2` in both modes).
- `strict-network` baseline: `NOT_ESTABLISHED` in this packet due DNS/network resolution failure.

## Escalation decision

T17 escalation rule:
- escalate if no baseline strict run can be established after hardening and fixture checks.

Observed:
- fixture checks passed (`from-file` and `replay` are both deterministic and non-zero).
- `strict-network` remains non-baseline (`exit_code=1`, `run_records_loaded=0`).

Decision:
- `ESCALATE_TO_L2` for strict baseline establishment blocker (`URLError` / DNS resolution failure).
