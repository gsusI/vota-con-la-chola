# AI-OPS-09 Tracker-row reconciliation evidence

## Scope
- Objective: Build deterministic status recommendations for tracker rows after apply/recompute and integrity evidence in AI-OPS-09.
- Inputs:
  - `docs/etl/e2e-scrape-load-tracker.md`
  - `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-packet.md`
  - `docs/etl/sprints/AI-OPS-09/reports/publish-parity-check.md`
- Contract used for mapping: `TRACKER_TIPO_SOURCE_HINTS` and `TRACKER_SOURCE_HINTS` in `scripts/graph_ui_server.py`.

## Deterministic evidence-backed status recommendations

| source_id | tracker_row | tracker_status | sql_status | mismatch_state | recommendation | evidence_path | blocker_note |
|---|---|---|---|---|---|---|---|
| placsp_autonomico | Contratación autonómica (piloto 3 CCAA) | TODO | DONE | MISMATCH | KEEP_TODO | `docs/etl/sprints/AI-OPS-09/reports/placsp-apply-recompute.md`; `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__strict-network.stdout.log`; `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__from-file.stdout.log`; `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__replay.stderr.log` | Replay path is non-deterministic (`wc -c = 0`) and replay command fails parse with `payload_sig=e3b0...`; strict-network/from-file evidence alone is not enough to promote to DONE without replay parity. |
| placsp_sindicacion | Contratacion publica (Espana) | TODO | DONE | MISMATCH | KEEP_TODO | `docs/etl/sprints/AI-OPS-09/reports/placsp-apply-recompute.md`; `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__strict-network.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__from-file.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__replay.stderr.log` | strict-network guard returns `TimeoutError`; replay fixture file is empty and XML parse fails (`ParseError no element found`). Cannot mark DONE without closed blocker.
| bdns_api_subvenciones | Subvenciones y ayudas (Espana) | TODO | PARTIAL | MISMATCH | KEEP_TODO | `docs/etl/sprints/AI-OPS-09/reports/bdns-apply-recompute.md`; `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__strict-network.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__replay.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-sql/bdns_api_subvenciones__from-file_run_snapshot.csv` | strict-network blocked by anti-HTML payload (`Respuesta HTML inesperada para BDNS feed`); replay fixture file is missing. Keep TODO and require contract or fixture parity fix first. |
| bdns_autonomico | Subvenciones autonómicas (piloto 3 CCAA) | TODO | PARTIAL | MISMATCH | KEEP_TODO | `docs/etl/sprints/AI-OPS-09/reports/bdns-apply-recompute.md`; `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__strict-network.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__replay.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-sql/bdns_autonomico__from-file_run_snapshot.csv` | strict-network blocked by anti-HTML payload; replay fixture is missing. Keep TODO until deterministic source replay is available. |
| eurostat_sdmx | Indicadores (outcomes): Eurostat | TODO | DONE | MISMATCH | KEEP_TODO | `docs/etl/sprints/AI-OPS-09/reports/eurostat-apply-recompute.md`; `docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_ES_unit_PC_ACT__strict-network.stdout.log`; `docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_ES_unit_PC_ACT__replay.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__replay_run_snapshot.csv` | strict-network ingest is successful, but from-file and replay fail and replay parity is `DRIFT` (`replay_loaded=0`). Keep TODO to avoid false gate satisfaction. |
| bde_series_api | Indicadores (confusores): Banco de España | TODO | PARTIAL | MISMATCH | KEEP_TODO | `docs/etl/sprints/AI-OPS-09/reports/bde-apply-recompute.md`; `docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/PARO_TASA_ES_M__strict-network.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/TI_TMM_T_4F_EUR_4F_N_M__replay.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/TI_TMM_T_4F_EUR_4F_N_M__replay_run_snapshot.csv` | strict-network and replay both fail (DNS or no parseable series payloads). Cannot move tracker state without replay closure. |
| aemet_opendata_series | Indicadores (confusores): AEMET | TODO | PARTIAL | MISMATCH | KEEP_TODO | `docs/etl/sprints/AI-OPS-09/reports/aemet-apply-recompute.md`; `docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_3195_tmed__strict-network.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_3195_tmed__replay.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-sql/station_3195_tmed__replay_source_records_snapshot.csv` | AEMET strict-network and replay fail with endpoint errors and zero records; no token/quota-stable replay window yet. Keep TODO and escalate blocker handling if token policy changes. |

## Deterministic next commands (row level)

| source_id | next_command |
|---|---|
| placsp_autonomico | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_autonomico --snapshot-date 2026-02-17 --strict-network --timeout 30` |
| placsp_sindicacion | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_sindicacion --snapshot-date 2026-02-17 --strict-network --timeout 60` |
| bdns_api_subvenciones | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_api_subvenciones --snapshot-date 2026-02-17 --strict-network --timeout 30` |
| bdns_autonomico | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_autonomico --snapshot-date 2026-02-17 --strict-network --timeout 30` |
| eurostat_sdmx | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source eurostat_sdmx --url https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_a --snapshot-date 2026-02-17 --strict-network --timeout 30` |
| bde_series_api | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bde_series_api --url https://api.bde.es/datos/series/PARO.TASA.ES.M --snapshot-date 2026-02-17 --strict-network --timeout 30` |
| aemet_opendata_series | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source aemet_opendata_series --url https://opendata.aemet.es/opendata/api/valores/climatologicos --snapshot-date 2026-02-17 --strict-network --timeout 30` |

## Unresolved rows
- `UNRESOLVED_COUNT: 0`
- Decision result: keep all seven rows in `TODO` until blockers are cleared, since current evidence indicates mismatch is caused by unclosed strict/replay/network constraints and promotion would create unverified gate claims.
