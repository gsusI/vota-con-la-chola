# PLACSP/BDNS Snapshot Adapter (T7)

Date:
- `2026-02-17`

Objective:
- Normalize PLACSP/BDNS run snapshot artifacts to canonical schema v2 while preserving legacy compatibility for existing report consumers.

## What changed

File updated:
- `scripts/ingestar_politicos_es.py`

New wrapper command:
- `normalize-run-snapshot` (alias: `adapt-run-snapshot`)

Behavior:
- normalizes legacy/tabular `*_run_snapshot.csv` to canonical schema v2.
- optional legacy output retained via `--legacy-kv-out` (`metric,value`).
- emits parity summary JSON with stable fields:
  - `source_id`
  - `mode`
  - `run_records_loaded`
  - `snapshot_date`
- fails fast on unusable inputs:
  - empty snapshot files
  - normalized outputs missing key fields (`source_id|mode|run_records_loaded`)

## Why this adapter exists

Current state:
- AI-OPS-09 PLACSP/BDNS snapshots include mixed formats (`metric,value`, tabular, and some empty files).
- This blocks deterministic parity readers if consumed directly.

Target state:
- one canonical run snapshot schema (v2) for strict/replay comparisons.
- legacy readers still supported during transition.

Next step:
- L1 apply/replay packets consume canonical v2 outputs by default and keep legacy outputs only where old report templates still read `metric,value`.

## Commands (migration/backfill)

Single file:
```bash
python3 scripts/ingestar_politicos_es.py normalize-run-snapshot \
  --in docs/etl/sprints/AI-OPS-09/evidence/bdns-ingest-logs/sql/bdns_autonomico__strict-network_run_snapshot.csv \
  --out docs/etl/sprints/AI-OPS-10/evidence/snapshot-adapter/bdns_autonomico__strict-network_run_snapshot.v2.csv \
  --legacy-kv-out docs/etl/sprints/AI-OPS-10/evidence/snapshot-adapter/legacy/bdns_autonomico__strict-network_run_snapshot.legacy.csv
```

Batch (skip empty source files):
```bash
for f in \
  docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-sql/*_run_snapshot.csv \
  docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-sql/*_run_snapshot.csv
do
  [ -s "$f" ] || { echo "SKIP empty $f"; continue; }
  base="$(basename "$f" .csv)"
  python3 scripts/ingestar_politicos_es.py normalize-run-snapshot \
    --in "$f" \
    --out "docs/etl/sprints/AI-OPS-10/evidence/snapshot-adapter/${base}.v2.csv" \
    --legacy-kv-out "docs/etl/sprints/AI-OPS-10/evidence/snapshot-adapter/legacy/${base}.legacy.csv"
done
```

## Counter interpretation (strict vs replay)

- `run_records_loaded`:
  - count of valid records processed in that run (primary parity comparator).
- `delta_records`:
  - DB cardinality delta (`after_records - before_records`).
  - can be `0` on replay/idempotent reruns even when `run_records_loaded > 0`.
- `exit_code` + `run_status`:
  - classify run success/failure.
  - use together with `run_records_loaded` for parity verdict (`PASS/DRIFT/BLOCKED`).

Rule of thumb for PLACSP/BDNS source-record connectors:
- parity should prioritize `source_id`, `mode`, `exit_code`, `run_records_loaded`, `snapshot_date`.
- do not treat `delta_records=0` alone as failure on replay/idempotent paths.

## Validation executed

Commands:
```bash
python3 scripts/ingestar_politicos_es.py normalize-run-snapshot --help
python3 scripts/ingestar_politicos_es.py normalize-run-snapshot \
  --in docs/etl/sprints/AI-OPS-09/evidence/bdns-ingest-logs/sql/bdns_autonomico__strict-network_run_snapshot.csv \
  --out docs/etl/sprints/AI-OPS-10/evidence/snapshot-adapter/bdns_autonomico__strict-network_run_snapshot.v2.csv \
  --legacy-kv-out docs/etl/sprints/AI-OPS-10/evidence/snapshot-adapter/legacy/bdns_autonomico__strict-network_run_snapshot.legacy.csv
```

Observed:
- valid BDNS snapshot normalized correctly with populated `source_id/mode/run_records_loaded`.
- empty PLACSP snapshot (`placsp_autonomico__strict-network_run_snapshot.csv`) now fails fast with explicit error (`snapshot vacio`) instead of producing blank artifacts.
