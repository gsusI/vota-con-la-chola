# AI-OPS-10 T18 AEMET Apply

Date:
- `2026-02-17`

Objective:
- Execute `aemet_opendata_series` strict/replay apply wave and capture parity outcomes with blocker classes.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
- `docs/etl/sprints/AI-OPS-10/reports/aemet-contract-hardening.md`
- `scripts/run_source_probe_matrix.sh`

## Replay fixture

Prepared replay input:
- `docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/aemet_opendata_series/aemet_opendata_series_replay_20260217.json`

## Output contract artifacts

Logs:
- `docs/etl/sprints/AI-OPS-10/evidence/aemet-logs/`

SQL snapshots:
- `docs/etl/sprints/AI-OPS-10/evidence/aemet-sql/`

Report:
- `docs/etl/sprints/AI-OPS-10/reports/aemet-apply.md`

## Result table (`source_id=aemet_opendata_series`)

1. `mode=strict-network`
- `exit_code=1`
- `run_status=error`
- `run_records_loaded=0`
- `run_records_seen=0`
- `run_id=245`
- blocker signature:
  - `aemet_blocker=contract; error_type=HTTPError; detail=HTTP Error 404: No Encontrado`

2. `mode=from-file`
- `exit_code=0`
- `run_status=ok`
- `run_records_loaded=2`
- `run_records_seen=2`
- `run_id=246`

3. `mode=replay`
- `exit_code=0`
- `run_status=ok`
- `run_records_loaded=2`
- `run_records_seen=2`
- `run_id=247`

Parity checks:
- `from-file` vs `replay`: `MATCH` (`run_records_loaded=2` in both modes).
- strict payload behavior not reproducible as successful baseline in this packet (`strict-network` blocked by `contract` class).

## Blocker class mapping

- `auth`: not observed in this packet.
- `contract`: observed (`HTTP Error 404`, `aemet_blocker=contract`).
- `network`: not observed in this packet.

## Escalation decision

T18 escalation rule:
- escalate if replay fixtures are valid but parser still cannot reproduce strict payload behavior.

Observed:
- replay fixtures valid and deterministic (`from-file` and `replay` both non-zero).
- strict path remains blocked (`contract`/404), so strict behavior could not be reproduced as a successful baseline.

Decision:
- `ESCALATE_TO_L2` for strict contract baseline blocker.
