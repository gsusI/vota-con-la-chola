# AI-OPS-10 T26 Throughput Blockers Refresh

Date:
- `2026-02-17`

Objective:
- Refresh carryover-source throughput/blocker taxonomy using T21 parity evidence and T22 postrun gate evidence.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/evidence/source-parity-sql/README.md`
- `docs/etl/sprints/AI-OPS-10/evidence/source-parity-sql/all_run_snapshots.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/source-parity-sql/strict_vs_replay_by_source.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.md`
- `docs/etl/sprints/AI-OPS-10/evidence/status-postrun.json`
- `docs/etl/sprints/AI-OPS-09/reports/throughput-blockers-summary.md`

## Throughput and replay status (carryover sources)

| family | source_id | strict_status | strict_loaded | from_file_loaded | replay_loaded | replay_vs_from_file | tracker_status | sql_status | mismatch_state |
|---|---|---:|---:|---:|---:|---|---|---|---|
| placsp | `placsp_autonomico` | `error` | `0` | `2` | `2` | `MATCH` | `PARTIAL` | `DONE` | `MISMATCH` |
| placsp | `placsp_sindicacion` | `error` | `0` | `3` | `3` | `MATCH` | `PARTIAL` | `DONE` | `MISMATCH` |
| bdns | `bdns_api_subvenciones` | `error` | `0` | `3` | `3` | `MATCH` | `PARTIAL` | `PARTIAL` | `MATCH` |
| bdns | `bdns_autonomico` | `error` | `0` | `2` | `2` | `MATCH` | `PARTIAL` | `PARTIAL` | `MATCH` |
| eurostat | `eurostat_sdmx` | `ok` | `2394` | `2` | `2` | `MATCH` | `PARTIAL` | `DONE` | `MISMATCH` |
| bde | `bde_series_api` | `error` | `0` | `2` | `2` | `MATCH` | `PARTIAL` | `PARTIAL` | `MATCH` |
| aemet | `aemet_opendata_series` | `error` | `0` | `2` | `2` | `MATCH` | `PARTIAL` | `PARTIAL` | `MATCH` |

Observations:
- Replay vs from-file parity is stable (`MATCH`) for all 7 carryover sources.
- Strict-network remains blocked for 6/7 sources; only `eurostat_sdmx` strict run is healthy and high-volume.
- T22 mismatches (`3`) are exactly `placsp_autonomico`, `placsp_sindicacion`, `eurostat_sdmx`.

## Blocker taxonomy refresh

| source_id | root_cause | blocker_signature | next command | evidence |
|---|---|---|---|---|
| `placsp_autonomico` | `network` | strict-network fails TLS verification (`CERTIFICATE_VERIFY_FAILED`) | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_autonomico --snapshot-date 2026-02-17 --strict-network --timeout 30` | `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql/placsp_autonomico__strict-network_run_snapshot.csv` |
| `placsp_sindicacion` | `network` | strict-network fails TLS verification (`CERTIFICATE_VERIFY_FAILED`) | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_sindicacion --snapshot-date 2026-02-17 --strict-network --timeout 60` | `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql/placsp_sindicacion__strict-network_run_snapshot.csv` |
| `bdns_api_subvenciones` | `auth` | strict-network receives anti-bot HTML (`Respuesta HTML inesperada para BDNS feed`) | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_api_subvenciones --snapshot-date 2026-02-17 --strict-network --timeout 30` | `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql/bdns_api_subvenciones__strict-network_run_snapshot.csv` |
| `bdns_autonomico` | `auth` | strict-network receives anti-bot HTML (`Respuesta HTML inesperada para BDNS feed`) | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_autonomico --snapshot-date 2026-02-17 --strict-network --timeout 30` | `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql/bdns_autonomico__strict-network_run_snapshot.csv` |
| `eurostat_sdmx` | `data_quality` | strict/replay ingestion is healthy; blocker is tracker/sql status lag (`PARTIAL` vs `DONE`) | `just etl-tracker-gate` | `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.log`; `docs/etl/sprints/AI-OPS-10/evidence/eurostat-sql/eurostat_sdmx__strict-network_run_snapshot.csv` |
| `bde_series_api` | `network` | strict-network fails DNS resolution (`Errno 8`) | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bde_series_api --url https://api.bde.es/datos/series/PARO.TASA.ES.M --snapshot-date 2026-02-17 --strict-network --timeout 30` | `docs/etl/sprints/AI-OPS-10/evidence/bde-sql/bde_series_api__strict-network_run_snapshot.csv` |
| `aemet_opendata_series` | `contract` | strict-network contract error (`aemet_blocker=contract`, HTTP 404) | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source aemet_opendata_series --url https://opendata.aemet.es/opendata/api/valores/climatologicos --snapshot-date 2026-02-17 --strict-network --timeout 30` | `docs/etl/sprints/AI-OPS-10/evidence/aemet-sql/aemet_opendata_series__strict-network_run_snapshot.csv` |

Taxonomy counts:
- `network`: `3`
- `auth`: `2`
- `contract`: `1`
- `data_quality`: `1`

## Escalation rule check

T26 escalation condition:
- escalate only if blocker class cannot be inferred from evidence and needs HI arbitration.

Observed:
- all 7 carryover sources have inferable classes from strict/replay snapshots and postrun gate evidence.

Decision:
- `NO_ESCALATION`.
