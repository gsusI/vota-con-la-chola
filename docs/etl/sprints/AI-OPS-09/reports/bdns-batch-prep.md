# AI-OPS-09 BDNS batch prep report

## Scope
- Build deterministic BDNS ingest command matrix for strict-network, from-file, and replay execution.
- Build sample manifest with deterministic checksum and field-level header checks.
- Prepare evidence paths and blocker handling rules for the apply/recompute phase.

## Contract source-of-truth
- `etl/politicos_es/config.py` contract entries used:
  - `bdns_api_subvenciones`: `min_records_loaded_strict=10`, `fallback_file=etl/data/raw/samples/bdns_api_subvenciones_sample.json`
  - `bdns_autonomico`: `min_records_loaded_strict=3`, `fallback_file=etl/data/raw/samples/bdns_autonomico_sample.json`
- CLI contract from `scripts/ingestar_politicos_es.py ingest --help`:
  - `--strict-network`
  - `--from-file FROM_FILE`
  - `--timeout TIMEOUT`
  - `--snapshot-date SNAPSHOT_DATE`

## Generated artifacts
- `docs/etl/sprints/AI-OPS-09/exports/bdns_ingest_matrix.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/bdns_sample_manifest.tsv`

## Field-level evidence manifest
- Built `docs/etl/sprints/AI-OPS-09/evidence/bdns_sample_manifest.tsv` from sample fixtures.
- For each source we recorded:
  - payload presence and status
  - byte size and SHA-256
  - top-level shape
  - per-row header field list
  - row counts for reproducibility checks
- Current status:
  - `bdns_api_subvenciones`: `status=OK`
  - `bdns_autonomico`: `status=OK`

## Command matrix
- See `docs/etl/sprints/AI-OPS-09/exports/bdns_ingest_matrix.csv`.
- Matrix includes:
  - `strict-network`
  - `from-file`
  - `replay`
- `replay` is intentionally modeled as a deterministic `--from-file` run against a captured snapshot (`docs/etl/sprints/AI-OPS-09/evidence/bdns-replay-inputs/*/*_replay_20260217.json`).

## Blocker handling rules
- If an upstream auth/contract regression is observed before apply, set blocker:
  - `source_id=<id>`
  - `blocker=BLOCKED_AUTH_CONTRACT`
  - evidence evidence paths must point to captured HTTP request/response artifacts
- If a sample file is missing in this prep phase:
  - set `status=BLOCKED_MISSING_SAMPLE` in `docs/etl/sprints/AI-OPS-09/evidence/bdns_sample_manifest.tsv`
  - stop apply phase for that source
- Replay input paths are pre-created directories only, and should be populated from deterministic prior runs.

## Evidence paths included in matrix
- stdout logs:
  - `docs/etl/sprints/AI-OPS-09/evidence/bdns-ingest-logs/*.stdout.log`
- stderr logs:
  - `docs/etl/sprints/AI-OPS-09/evidence/bdns-ingest-logs/*.stderr.log`
- SQL snapshots:
  - `docs/etl/sprints/AI-OPS-09/evidence/bdns-ingest-logs/sql/*_run_snapshot.csv`
  - `docs/etl/sprints/AI-OPS-09/evidence/bdns-ingest-logs/sql/*_source_records_snapshot.csv`

## Acceptance checks
- `test -f docs/etl/sprints/AI-OPS-09/exports/bdns_ingest_matrix.csv`
- `rg -n "strict-network|from-file|replay" docs/etl/sprints/AI-OPS-09/exports/bdns_ingest_matrix.csv`
