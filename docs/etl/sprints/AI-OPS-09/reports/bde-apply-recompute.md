# BDE apply/recompute report
Timestamp: 2026-02-17T08:47:48.278292Z
DB: etl/data/staging/politicos-es.db
Snapshot date: 2026-02-17

## Executed matrix rows
| series_id | mode | exit_code | seen | loaded | run_id | status | run_snapshot | source_snapshot | command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PARO.TASA.ES.M | strict-network | 1 | 0 | 0 | 215 | error | docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/PARO_TASA_ES_M__strict-network_run_snapshot.csv | docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/PARO_TASA_ES_M__strict-network_source_records_snapshot.csv | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bde_series_api --url https://api.bde.es/datos/series/PARO.TASA.ES.M --snapshot-date 2026-02-17 --strict-network --timeout 30` |
| PARO.TASA.ES.M | replay | 1 | 0 | 0 | 216 | error | docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/PARO_TASA_ES_M__replay_run_snapshot.csv | docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/PARO_TASA_ES_M__replay_source_records_snapshot.csv | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bde_series_api --from-file docs/etl/sprints/AI-OPS-09/evidence/bde-replay-inputs/PARO_TASA_ES_M/PARO_TASA_ES_M_replay_20260217.json --snapshot-date 2026-02-17 --timeout 30` |
| TI.TMM.T.4F.EUR.4F.N.M | strict-network | 1 | 0 | 0 | 217 | error | docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/TI_TMM_T_4F_EUR_4F_N_M__strict-network_run_snapshot.csv | docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/TI_TMM_T_4F_EUR_4F_N_M__strict-network_source_records_snapshot.csv | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bde_series_api --url https://api.bde.es/datos/series/TI.TMM.T.4F.EUR.4F.N.M --snapshot-date 2026-02-17 --strict-network --timeout 30` |
| TI.TMM.T.4F.EUR.4F.N.M | replay | 1 | 0 | 0 | 218 | error | docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/TI_TMM_T_4F_EUR_4F_N_M__replay_run_snapshot.csv | docs/etl/sprints/AI-OPS-09/evidence/bde-ingest-logs/sql/TI_TMM_T_4F_EUR_4F_N_M__replay_source_records_snapshot.csv | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bde_series_api --from-file docs/etl/sprints/AI-OPS-09/evidence/bde-replay-inputs/TI_TMM_T_4F_EUR_4F_N_M/TI_TMM_T_4F_EUR_4F_N_M_replay_20260217.json --snapshot-date 2026-02-17 --timeout 30` |

## Replay parity
| series_id | strict_exit | replay_exit | strict_loaded | replay_loaded | parity | delta_loaded |
| --- | --- | --- | --- | --- | --- | --- |
| PARO.TASA.ES.M | 1 | 1 | 0 | 0 | PASS | 0 |
| TI.TMM.T.4F.EUR.4F.N.M | 1 | 1 | 0 | 0 | PASS | 0 |

## Logs and snapshots
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/PARO_TASA_ES_M__replay.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/PARO_TASA_ES_M__replay.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/PARO_TASA_ES_M__strict-network.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/PARO_TASA_ES_M__strict-network.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/TI_TMM_T_4F_EUR_4F_N_M__replay.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/TI_TMM_T_4F_EUR_4F_N_M__replay.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/TI_TMM_T_4F_EUR_4F_N_M__strict-network.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-logs/TI_TMM_T_4F_EUR_4F_N_M__strict-network.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-sql/PARO_TASA_ES_M__replay_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-sql/PARO_TASA_ES_M__replay_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-sql/PARO_TASA_ES_M__strict-network_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-sql/PARO_TASA_ES_M__strict-network_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-sql/TI_TMM_T_4F_EUR_4F_N_M__replay_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-sql/TI_TMM_T_4F_EUR_4F_N_M__replay_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-sql/TI_TMM_T_4F_EUR_4F_N_M__strict-network_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/bde-apply-sql/TI_TMM_T_4F_EUR_4F_N_M__strict-network_source_records_snapshot.csv

## Quarantine / unresolved rows
- Blocked or failed rows are quarantined; execution continues for remaining rows.
- PARO.TASA.ES.M (strict-network): exit=1 reason=Traceback (most recent call last):   File "/opt/homebrew/Cellar/python@3.11/3.11.14_3/Frameworks/Python.framework/Versions/3.11/lib/python3.11/urllib/request.py", line 1348, in do_open     h.request(req.get_method(), req.selector, req.data, headers,   File "/opt/homebrew/Cellar/python@3.11/3.11.14_3/Frameworks/Python.framework/Versions/3.11/lib/python3.11/http/client.py", line 1303, in request    
- PARO.TASA.ES.M (replay): exit=1 reason=Traceback (most recent call last):   File "/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/scripts/ingestar_politicos_es.py", line 22, in <module>     raise SystemExit(main())                      ^^^^^^   File "/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/politi
- TI.TMM.T.4F.EUR.4F.N.M (strict-network): exit=1 reason=Traceback (most recent call last):   File "/opt/homebrew/Cellar/python@3.11/3.11.14_3/Frameworks/Python.framework/Versions/3.11/lib/python3.11/urllib/request.py", line 1348, in do_open     h.request(req.get_method(), req.selector, req.data, headers,   File "/opt/homebrew/Cellar/python@3.11/3.11.14_3/Frameworks/Python.framework/Versions/3.11/lib/python3.11/http/client.py", line 1303, in request    
- TI.TMM.T.4F.EUR.4F.N.M (replay): exit=1 reason=Traceback (most recent call last):   File "/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/scripts/ingestar_politicos_es.py", line 22, in <module>     raise SystemExit(main())                      ^^^^^^   File "/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/politi
