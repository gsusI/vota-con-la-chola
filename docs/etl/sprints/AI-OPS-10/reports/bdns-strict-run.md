# AI-OPS-10 T14 BDNS Strict Run

Date:
- `2026-02-17`

Objective:
- Execute `strict-network` rows for `bdns_api_subvenciones` and `bdns_autonomico`, persist logs/snapshots, and record anti-bot/HTML signatures.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
- `scripts/run_source_probe_matrix.sh`
- `etl/data/staging/politicos-es.db`

## Commands executed

```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv \
  --row-id bdns_autonomico__strict-network \
  --out-dir docs/etl/sprints/AI-OPS-10/evidence/bdns-strict \
  --allow-failures
```

```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv \
  --row-id bdns_api_subvenciones__strict-network \
  --out-dir docs/etl/sprints/AI-OPS-10/evidence/bdns-strict \
  --allow-failures
```

## Output contract artifacts

Logs:
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-logs/bdns_api_subvenciones__strict-network.stdout.log`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-logs/bdns_api_subvenciones__strict-network.stderr.log`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-logs/bdns_autonomico__strict-network.stdout.log`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-logs/bdns_autonomico__strict-network.stderr.log`

SQL snapshots:
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql/bdns_api_subvenciones__strict-network_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql/bdns_api_subvenciones__strict-network_source_records_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql/bdns_autonomico__strict-network_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql/bdns_autonomico__strict-network_source_records_snapshot.csv`

## Per-source counters

1. `bdns_api_subvenciones` (`strict-network`)
- `exit_code=1`
- `run_status=error`
- `run_records_seen=0`
- `run_records_loaded=0`
- `before_records=3`
- `after_records=3`
- `delta_records=0`
- `run_id=233`

2. `bdns_autonomico` (`strict-network`)
- `exit_code=1`
- `run_status=error`
- `run_records_seen=0`
- `run_records_loaded=0`
- `before_records=2`
- `after_records=2`
- `delta_records=0`
- `run_id=234`

## Anti-bot/HTML signatures

Observed signature in both sources:
- `RuntimeError: Respuesta HTML inesperada para BDNS feed (payload_sig=0401a40b059385b8a4d3e2fd933fe16213e22dd72df2f2fe2cdbd2872114c2fa)`

Interpretation:
- strict-mode request returned HTML instead of expected structured BDNS JSON payload.
- this is a classified runbook signature (`auth/waf/html` family), not an unclassified payload type.

Escalation rule check:
- T14 escalates only for unclassified payload types.
- `NO_ESCALATION` for this packet (classified HTML blocker captured with deterministic payload signature).
