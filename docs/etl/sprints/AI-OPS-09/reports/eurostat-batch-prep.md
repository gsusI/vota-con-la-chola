# AI-OPS-09 Eurostat batch prep report

## Scope
- Build deterministic Eurostat series manifest from curated sample payload.
- Build per-series ingest/replay matrix.
- Capture schema/header validation outcomes and blocker handling behavior.

## Inputs
- Connector contract: `etl/politicos_es/config.py` (`source_id=eurostat_sdmx`)
- Parser contract: `etl/politicos_es/connectors/eurostat_indicators.py`
- Sample input: `etl/data/raw/samples/eurostat_sdmx_sample.json`
- CLI: `scripts/ingestar_politicos_es.py ingest`

## Contract highlights
- `default_url`: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/`
- Connector format: JSON-stat (`id`, `size`, `dimension`, `value`)
- Output source record ID strategy:
  - `series:<sha24(series_code)>`

## Schema/header validation outcomes
- Sample load result:
  - top-level keys: `version`, `class`, `label`, `id`, `size`, `dimension`, `value`, `extension`
  - extension includes `datasetId`
- Parsed dataset:
  - `dataset=une_rt_a`
  - dimension ids: `freq`, `unit`, `geo`, `time`
  - total parsed series: `2`
  - total parsed rows in manifest: `2`
- Series header checks:
  - required fields present: `id`, `dataset`, `dimensions`, `frequency`
  - frequency values: only `A` (Annual)
  - unit values: `PC_ACT` (single unit)
- `UNRESOLVED_SERIES`: `0`
- `apply_set` candidates: `2` (all `TRUE`)

## Generated artifacts
- `docs/etl/sprints/AI-OPS-09/exports/eurostat_series_manifest.csv`
- `docs/etl/sprints/AI-OPS-09/exports/eurostat_ingest_matrix.csv`

## Ingest matrix strategy
- Matrix is generated for each manifest row and includes:
  - `strict-network`
  - `from-file`
  - `replay`
- Replay inputs are deterministic placeholders and must be populated with captured, reproducible captures before execute.
- Per-row `from-file` and `replay` commands are stored under:
  - `docs/etl/sprints/AI-OPS-09/evidence/eurostat-series-samples/*.json`
  - `docs/etl/sprints/AI-OPS-09/evidence/eurostat-replay-inputs/<series_id>/...`
- Per-row execution evidence paths are in:
  - `docs/etl/sprints/AI-OPS-09/evidence/eurostat-ingest-logs/*.stdout.log`
  - `docs/etl/sprints/AI-OPS-09/evidence/eurostat-ingest-logs/*.stderr.log`
  - `docs/etl/sprints/AI-OPS-09/evidence/eurostat-ingest-logs/sql/*_run_snapshot.csv`
  - `docs/etl/sprints/AI-OPS-09/evidence/eurostat-ingest-logs/sql/*_source_records_snapshot.csv`

## Escalation rule for ambiguity
- If a series row has missing frequency/unit/dataset/dimensions, set:
  - `status=UNRESOLVED_SERIES`
  - `apply_set=FALSE`
- Such rows are excluded from apply set until ambiguity is resolved by evidence.

## Acceptance checks
- `test -f docs/etl/sprints/AI-OPS-09/exports/eurostat_series_manifest.csv`
- `rg -n "dataset|series|frequency" docs/etl/sprints/AI-OPS-09/exports/eurostat_series_manifest.csv`
