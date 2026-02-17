# AI-OPS-09 BDE batch prep report

## Scope
- Build deterministic Banco de España (BDE) series manifest.
- Build strict-network + replay matrix for apply-ready series.
- Add schema/header/field validation outcomes and blocked series handling.

## Inputs
- Connector contract: `etl/politicos_es/config.py` (`source_id=bde_series_api`)
- Connector parser: `etl/politicos_es/connectors/bde_series.py`
- CLI contract: `scripts/ingestar_politicos_es.py ingest`
- Sample fixture: `etl/data/raw/samples/bde_series_api_sample.json`

## Validation findings from fixture
- Top-level payload loaded from sample successfully.
- Parsed series count (from `parse_bde_records`): `2`
- Required fields presence:
  - `series_code` present for both rows.
  - `frequency` present for both rows.
  - `unit` present for both rows.
- Derived dimensions:
  - `series_code`, `freq`, `unit`
- Stable metadata for all rows: `TRUE`
- Apply blockers (`UNRESOLVED_SERIES`): `0`

## Artifacts generated
- `docs/etl/sprints/AI-OPS-09/exports/bde_series_manifest.csv`
- `docs/etl/sprints/AI-OPS-09/exports/bde_ingest_matrix.csv`

## Matrix policy
- Modes produced:
  - `strict-network`
  - `replay`
- `strict-network` commands target per-series endpoint using the row source URL when available (`--url <source_url>`).
- `replay` mode uses per-series deterministic replay payload placeholders under `docs/etl/sprints/AI-OPS-09/evidence/bde-replay-inputs/<safe_id>/`.

## Blocker and escalation policy
- If a row lacks stable `series_code`, `frequency`, or `unit`, mark:
  - `status=UNRESOLVED_SERIES`
  - `apply_set=FALSE`
  - exclude row from `bde_ingest_matrix.csv`
- Escalation evidence for blockers should include schema/header evidence and exact missing field list.

## Evidence path contract
- command logs:
  - `docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/*.stdout.log`
  - `docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/*.stderr.log`
- SQL snapshots:
  - `docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/*_run_snapshot.csv`
  - `docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/*_source_records_snapshot.csv`
- replay fixtures:
  - `docs/etl/sprints/AI-OPS-09/evidence/bde-replay-inputs/<safe_series_id>/<safe_series_id>_replay_20260217.json`

## Acceptance checks
- `test -f docs/etl/sprints/AI-OPS-09/exports/bde_series_manifest.csv`
- `rg -n "series|unit|frequency" docs/etl/sprints/AI-OPS-09/exports/bde_series_manifest.csv`
