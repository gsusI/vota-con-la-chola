# HI Handoff Runbook (T10)

Date:
- `2026-02-17`

Objective:
- Freeze the `source_probe_matrix` packet and execution sequence so FAST/L1 can run the carryover sources without ambiguity.

## Frozen inputs

- Matrix file:
  - `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv`
- Runner:
  - `scripts/run_source_probe_matrix.sh`
- Contract references:
  - `docs/etl/sprints/AI-OPS-10/reports/contract-schema-normalization.md`
  - `docs/etl/sprints/AI-OPS-10/reports/eurostat-contract-hardening.md`
  - `docs/etl/sprints/AI-OPS-10/reports/bde-contract-hardening.md`
  - `docs/etl/sprints/AI-OPS-10/reports/aemet-contract-hardening.md`
  - `docs/etl/sprints/AI-OPS-10/reports/placsp-bdns-snapshot-adapter.md`
  - `docs/etl/sprints/AI-OPS-10/reports/contract-tests.md`

Frozen matrix fingerprint:
- rows: `21`
- sha256: `178fb00cbc55f54f01e727032b16ab59be76b541d7dc0f9a96fddf5cf43085e3`

Freeze rule:
- If `source_probe_matrix.tsv` content changes (hash mismatch), this runbook is stale and must be regenerated before execution.

## Frozen execution order

Run all commands from repository root.

1. Packet preflight
```bash
bash scripts/run_source_probe_matrix.sh --help
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv \
  --dry-run
```

2. Wave A (`from-file`) in frozen source order
```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv \
  --mode from-file
```

3. Wave B (`strict-network`) in frozen source order
```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv \
  --mode strict-network \
  --allow-failures
```

4. Wave C (`replay`) in frozen source order
```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv \
  --mode replay \
  --allow-failures
```

Frozen row order (source packet):
1. `placsp_autonomico__strict-network`
2. `placsp_autonomico__from-file`
3. `placsp_autonomico__replay`
4. `bdns_autonomico__strict-network`
5. `bdns_autonomico__from-file`
6. `bdns_autonomico__replay`
7. `placsp_sindicacion__strict-network`
8. `placsp_sindicacion__from-file`
9. `placsp_sindicacion__replay`
10. `bdns_api_subvenciones__strict-network`
11. `bdns_api_subvenciones__from-file`
12. `bdns_api_subvenciones__replay`
13. `eurostat_sdmx__strict-network`
14. `eurostat_sdmx__from-file`
15. `eurostat_sdmx__replay`
16. `bde_series_api__strict-network`
17. `bde_series_api__from-file`
18. `bde_series_api__replay`
19. `aemet_opendata_series__strict-network`
20. `aemet_opendata_series__from-file`
21. `aemet_opendata_series__replay`

## Mandatory artifact contract

For every `source_id` and `mode` row in `source_probe_matrix`, artifacts are mandatory.

Row identity:
- `row_id = <source_id>__<mode>`

Default artifact paths (when `--out-dir` is omitted):
- `docs/etl/sprints/AI-OPS-10/evidence/source-probe-logs/<row_id>.stdout.log`
- `docs/etl/sprints/AI-OPS-10/evidence/source-probe-logs/<row_id>.stderr.log`
- `docs/etl/sprints/AI-OPS-10/evidence/source-probe-sql/<row_id>_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/source-probe-sql/<row_id>_source_records_snapshot.csv`
- run summary artifact:
  - `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.run-summary.tsv`

If `--out-dir <DIR>` is used, required artifact paths are remapped deterministically:
- `<DIR>/logs/<row_id>.stdout.log`
- `<DIR>/logs/<row_id>.stderr.log`
- `<DIR>/sql/<row_id>_run_snapshot.csv`
- `<DIR>/sql/<row_id>_source_records_snapshot.csv`
- `<DIR>/probe_runner_summary.tsv`

Run snapshot schema gate (must pass for every non-dry row):
- CSV exists and has canonical fields from `normalized_run_snapshot_v2`:
  - `schema_version,source_id,mode,exit_code,run_records_loaded,snapshot_date,...`

## Escalation thresholds

Use these deterministic escalation gates for the packet.

1. `escalation=auth_waf_html` (strict blocker, immediate)
- Trigger:
  - strict row `status=error`, and stderr contains any of:
    - `HTTP Error 401`
    - `HTTP Error 403`
    - `cloudflare`
    - `cf-mitigated`
    - `Respuesta HTML inesperada`
    - `aemet_blocker=auth`
- Action:
  - mark source/mode `BLOCKED_AUTH_WAF_HTML`
  - no repeated blind retries in the same run packet
  - continue remaining rows and capture artifacts

2. `escalation=replay_drift` (contract drift)
- Trigger:
  - `from-file` row is `ok` with `run_records_loaded > 0`, but matching `replay` row has:
    - `status=error`, or
    - `exit_code != 0`, or
    - `run_records_loaded = 0`, or
    - missing canonical run snapshot artifact
- Action:
  - mark source `REPLAY_DRIFT`
  - attach strict/from-file/replay triplet artifacts
  - stop claiming parity for that source

3. `escalation=artifact_missing` (packet integrity)
- Trigger:
  - any required artifact path for a executed row is missing.
- Action:
  - mark packet `INVALID_ARTIFACT_SET`
  - rerun only affected row after fixing filesystem/path issue

4. `escalation=contract_payload` (wrong replay fixture class)
- Trigger:
  - stderr contains payload contract signatures such as:
    - `metric,value`
    - `snapshot vacio`
    - `No se encontraron ... parseables`
    - `aemet_blocker=contract`
- Action:
  - mark source `BLOCKED_CONTRACT_INPUT`
  - replace replay input with capture-compatible payload

## Fast validation commands

Matrix/hash check:
```bash
python3 - <<'PY'
import hashlib
from pathlib import Path
p = Path("docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv")
print(hashlib.sha256(p.read_bytes()).hexdigest())
PY
```

Summary scan for non-ok rows:
```bash
awk -F '\t' 'NR==1 || $4!="ok"' docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.run-summary.tsv
```

Escalation signature scan:
```bash
rg -n "HTTP Error 401|HTTP Error 403|cloudflare|cf-mitigated|Respuesta HTML inesperada|aemet_blocker=auth|aemet_blocker=contract|metric,value|snapshot vacio" \
  docs/etl/sprints/AI-OPS-10/evidence/source-probe-logs/*.stderr.log
```
