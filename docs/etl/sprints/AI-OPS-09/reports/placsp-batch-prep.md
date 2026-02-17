# AI-OPS-09 PLACSP batch prep report

## Scope
- Build deterministic PLACSP ingest command matrix for strict-network, from-file, and replay execution.
- Validate sample availability in `etl/data/raw/samples/`.
- Keep command logs and SQL evidence paths as reproducible placeholders for apply execution.

## Contract source-of-truth
- `etl/politicos_es/config.py` contract entries used:
  - `placsp_sindicacion`: `min_records_loaded_strict=10`, `fallback_file=etl/data/raw/samples/placsp_sindicacion_sample.xml`
  - `placsp_autonomico`: `min_records_loaded_strict=3`, `fallback_file=etl/data/raw/samples/placsp_autonomico_sample.xml`
- CLI contract from `scripts/ingestar_politicos_es.py ingest --help`:
  - `--strict-network`
  - `--from-file FROM_FILE`
  - `--timeout TIMEOUT`
  - `--snapshot-date SNAPSHOT_DATE`

## Generated artifacts
- `docs/etl/sprints/AI-OPS-09/exports/placsp_ingest_matrix.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/placsp_sample_manifest.tsv`

## Sample manifest (checksum + record hints)
- Built `docs/etl/sprints/AI-OPS-09/evidence/placsp_sample_manifest.tsv` directly from sample fixtures and configured `fallback_file` paths.
- `status=OK` for all required PLACSP samples.
- Escalation state: `BLOCKED_MISSING_SAMPLE` not set (no missing sample files).

## Placeholder command logs / evidence paths
All CSV rows include per-mode log and snapshot placeholders:
- `docs/etl/sprints/AI-OPS-09/evidence/placsp-ingest-logs/*.stdout.log`
- `docs/etl/sprints/AI-OPS-09/evidence/placsp-ingest-logs/*.stderr.log`
- `docs/etl/sprints/AI-OPS-09/evidence/placsp-ingest-logs/sql/*_run_snapshot.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/placsp-ingest-logs/sql/*_source_records_snapshot.csv`

Replay placeholders are pre-allocated under:
- `docs/etl/sprints/AI-OPS-09/evidence/placsp-replay-inputs/placsp_sindicacion/`
- `docs/etl/sprints/AI-OPS-09/evidence/placsp-replay-inputs/placsp_autonomico/`

## Command matrix
- See all prepared commands in:
  - `docs/etl/sprints/AI-OPS-09/exports/placsp_ingest_matrix.csv`
- Matrix includes explicit rows for:
  - `strict-network`
  - `from-file`
  - `replay`

## Notes
- `replay` mode is intentionally `--from-file` replay of a captured deterministic fixture.
- Replay input paths are placeholders and must be populated with captured raw fixtures before execution.

## Acceptance checks
- `test -f docs/etl/sprints/AI-OPS-09/exports/placsp_ingest_matrix.csv`
- `rg -n "strict-network|from-file|replay" docs/etl/sprints/AI-OPS-09/exports/placsp_ingest_matrix.csv`
