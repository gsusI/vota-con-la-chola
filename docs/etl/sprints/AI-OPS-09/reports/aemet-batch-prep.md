# AI-OPS-09 AEMET batch prep report

## Scope
- Build deterministic AEMET station manifest from the connector sample payload.
- Build a deterministic ingest/replay matrix for selected AEMET series.
- Record token and quota failure handling for network-only execution mode.

## Inputs
- Connector contract: `etl/politicos_es/config.py` (`source_id=aemet_opendata_series`, `default_url=https://opendata.aemet.es/opendata/api/valores/climatologicos`).
- Connector implementation: `etl/politicos_es/connectors/aemet_indicators.py`.
- Sample fixture: `etl/data/raw/samples/aemet_opendata_series_sample.json`.
- Runner contract: `scripts/ingestar_politicos_es.py ingest`.

## Deterministic derivation
- Snapshot date pinned: `2026-02-17`.
- Station manifest source rows: `2` (`3195`, `0076`).
- Series rows derived from sample: `2` (`station:3195:var:tmed`, `station:0076:var:prec`).
- Output manifest includes station metadata and selected series tags in deterministic order.

## Produced artifacts
- `docs/etl/sprints/AI-OPS-09/exports/aemet_station_manifest.csv`
- `docs/etl/sprints/AI-OPS-09/exports/aemet_ingest_matrix.csv`

## Command matrix
- Strict-network mode per selected series:
  - `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source aemet_opendata_series --url https://opendata.aemet.es/opendata/api/valores/climatologicos --snapshot-date 2026-02-17 --strict-network --timeout 30`
- Replay mode per selected series:
  - `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source aemet_opendata_series --from-file <series_replay_json> --snapshot-date 2026-02-17 --timeout 30`
- Replay placeholders are placed in:
  - `docs/etl/sprints/AI-OPS-09/evidence/aemet-replay-inputs/station_3195_tmed/station_3195_tmed_replay_20260217.json`
  - `docs/etl/sprints/AI-OPS-09/evidence/aemet-replay-inputs/station_0076_prec/station_0076_prec_replay_20260217.json`

## Token and quota policy
- Token contract:
  - If `AEMET_API_KEY` is present, connector appends `api_key` to request URL.
  - If token is missing and endpoint requires token substitution (template `{api_key}`), strict mode fails fast.
- In strict-network runs, any auth/quota/network errors (including token expiry, HTTP 429, etc.) must fail immediately and mark matrix rows with `BLOCKED_TOKEN` in the blocker notes.
- Escalation behavior:
  - Do not execute replay or write partial writes while strict-network indicates token/quota failure.
  - Preserve exact command output and stop before mutating output writes for those blocked rows.

## Evidence path contract
- stdout logs:
  - `docs/etl/sprints/AI-OPS-09/evidence/aemet-ingest-logs/*.stdout.log`
- stderr logs:
  - `docs/etl/sprints/AI-OPS-09/evidence/aemet-ingest-logs/*.stderr.log`
- SQL snapshots:
  - `docs/etl/sprints/AI-OPS-09/evidence/aemet-ingest-logs/sql/*_run_snapshot.csv`
  - `docs/etl/sprints/AI-OPS-09/evidence/aemet-ingest-logs/sql/*_source_records_snapshot.csv`

## Blocker handling and escalation rules
- If token or quota limits block reproducibility, mark affected rows as unresolved and escalate with full command output captured under `aemet-ingest-logs`.
- Resume only after re-running strict-network with valid token/known quota ceiling.

## Acceptance checks
- `test -f docs/etl/sprints/AI-OPS-09/exports/aemet_station_manifest.csv`
- `test -f docs/etl/sprints/AI-OPS-09/exports/aemet_ingest_matrix.csv`
- `rg -n "station|series|token" docs/etl/sprints/AI-OPS-09/reports/aemet-batch-prep.md`
