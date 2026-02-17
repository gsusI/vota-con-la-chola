# Strict Probe Runner (T8)

Date:
- `2026-02-17`

Objective:
- Provide one deterministic command entrypoint to execute probe-matrix rows and emit canonical logs/artifacts for L1 throughput packets.

## Delivered artifacts

- `scripts/run_source_probe_matrix.sh`
- `docs/etl/sprints/AI-OPS-10/reports/strict-probe-runner.md`

## Runner contract

Primary command:
```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv
```

Required options supported:
- `--matrix`
- `--out-dir`
- `--db`
- `--snapshot-date`

Additional execution controls:
- `--row-id`
- `--source-id`
- `--mode`
- `--allow-failures`
- `--dry-run`

## Deterministic output paths

Default behavior (`--out-dir` omitted):
- uses per-row paths embedded in matrix columns:
  - `expected_stdout_log`
  - `expected_stderr_log`
  - `expected_run_snapshot_csv`
  - `expected_source_records_snapshot_csv`

With `--out-dir <dir>`:
- writes deterministic row-id keyed files under:
  - `<dir>/logs/<row_id>.stdout.log`
  - `<dir>/logs/<row_id>.stderr.log`
  - `<dir>/sql/<row_id>_run_snapshot.csv`
  - `<dir>/sql/<row_id>_source_records_snapshot.csv`
- summary:
  - `<dir>/probe_runner_summary.tsv`

Without `--out-dir`, summary path:
- `$(dirname <matrix>)/source_probe_matrix.run-summary.tsv`

## Non-zero handling (report-friendly)

For each row, runner captures:
- `status` (`ok|error|dry-run`)
- `exit_code`
- `started_at`
- `finished_at`
- artifact paths
- `note` with compact failure signature (`command_exit=<code>; tail=<stderr_tail>`)

Execution model:
- continues through all rows even when one row fails.
- exits `1` if any row failed (unless `--allow-failures` is set).

This gives deterministic packet behavior:
- one run produces a complete summary TSV and per-row artifacts, not partial opaque failures.

## Snapshot artifact behavior

After each row execution (non-dry-run), runner emits:
- canonical run snapshot via:
  - `python3 scripts/ingestar_politicos_es.py export-run-snapshot ... --out <run_snapshot_csv>`
- source-records snapshot CSV (latest run metadata + total source_records count for that source).

## L1 usage examples

Run one strict row only:
```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv \
  --row-id bdns_autonomico__strict-network
```

Run replay rows only with DB override:
```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv \
  --mode replay \
  --db etl/data/staging/politicos-es.db
```

Dry-run preflight:
```bash
bash scripts/run_source_probe_matrix.sh \
  --matrix docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv \
  --dry-run \
  --out-dir docs/etl/sprints/AI-OPS-10/evidence/probe-runner-dryrun \
  --allow-failures
```

## Validation executed

- `bash scripts/run_source_probe_matrix.sh --help`
- `bash -n scripts/run_source_probe_matrix.sh`

Result:
- PASS
