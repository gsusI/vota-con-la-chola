# AI-OPS-10 T12 PLACSP Strict Run

Date:
- `2026-02-17`

Objective:
- Execute `strict-network` rows for `placsp_autonomico` and `placsp_sindicacion`, capture normalized snapshots/logs, and record loaded counters plus failure signatures.

## Inputs used

- Matrix:
  - `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
- Runner:
  - `scripts/run_source_probe_matrix.sh`
- DB:
  - `etl/data/staging/politicos-es.db`

## Commands executed

```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv \
  --row-id placsp_autonomico__strict-network \
  --out-dir docs/etl/sprints/AI-OPS-10/evidence/placsp-strict \
  --allow-failures
```

```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv \
  --row-id placsp_sindicacion__strict-network \
  --out-dir docs/etl/sprints/AI-OPS-10/evidence/placsp-strict \
  --allow-failures
```

## Output contract artifacts

Logs:
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-logs/placsp_autonomico__strict-network.stdout.log`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-logs/placsp_autonomico__strict-network.stderr.log`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-logs/placsp_sindicacion__strict-network.stdout.log`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-logs/placsp_sindicacion__strict-network.stderr.log`

SQL snapshots:
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql/placsp_autonomico__strict-network_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql/placsp_autonomico__strict-network_source_records_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql/placsp_sindicacion__strict-network_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql/placsp_sindicacion__strict-network_source_records_snapshot.csv`

## Per-source results

1. `placsp_autonomico` (`strict-network`)
- `exit_code=1`
- `run_status=error`
- `run_records_seen=0`
- `run_records_loaded=0`
- `before_records=108`
- `after_records=108`
- `delta_records=0`
- failure signature:
  - `urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self signed certificate in certificate chain (_ssl.c:1129)>`

2. `placsp_sindicacion` (`strict-network`)
- `exit_code=1`
- `run_status=error`
- `run_records_seen=0`
- `run_records_loaded=0`
- `before_records=109`
- `after_records=109`
- `delta_records=0`
- failure signature:
  - `urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self signed certificate in certificate chain (_ssl.c:1129)>`

## Escalation decision

T12 escalation rule:
- escalate to L2 only when strict payload shape diverges from expected parser contract.

Observed blocker:
- TLS certificate verification failure before payload parsing (`CERTIFICATE_VERIFY_FAILED`), same signature for both PLACSP strict rows.

Decision:
- `NO_L2_ESCALATION_FOR_PARSER_DRIFT` (blocker is upstream/TLS trust chain, not parser payload-shape divergence).
- mark strict rows as blocked by environment/network trust condition for this run packet.
