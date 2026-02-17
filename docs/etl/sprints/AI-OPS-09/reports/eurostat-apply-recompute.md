# Eurostat apply/recompute report
Timestamp: 2026-02-17T08:47:08.496334Z
DB: etl/data/staging/politicos-es.db
Snapshot: 2026-02-17

## Executed matrix rows

| series_id | mode | exit_code | seen | loaded | run_id | run_status | source_record_id | command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| une_rt_a|freq=A|geo=ES|unit=PC_ACT | strict-network | 0 | 2394 | 2394 | 209 | ok | series:4468f558922332ed237bf17f | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source eurostat_sdmx --url https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_a --snapshot-date 2026-02-17 --strict-network --timeout 30` |
| une_rt_a|freq=A|geo=ES|unit=PC_ACT | from-file | 1 | 0 | 0 | 210 | error | series:4468f558922332ed237bf17f | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source eurostat_sdmx --from-file docs/etl/sprints/AI-OPS-09/evidence/eurostat-series-samples/une_rt_a_freq_A_geo_ES_unit_PC_ACT.json --snapshot-date 2026-02-17 --timeout 30` |
| une_rt_a|freq=A|geo=ES|unit=PC_ACT | replay | 1 | 0 | 0 | 211 | error | series:4468f558922332ed237bf17f | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source eurostat_sdmx --from-file docs/etl/sprints/AI-OPS-09/evidence/eurostat-replay-inputs/une_rt_a_freq_A_geo_ES_unit_PC_ACT/une_rt_a_freq_A_geo_ES_unit_PC_ACT_replay_20260217.json --snapshot-date 2026-02-17 --timeout 30` |
| une_rt_a|freq=A|geo=PT|unit=PC_ACT | strict-network | 0 | 2394 | 2394 | 212 | ok | series:3feb2dae20867f4bf608324a | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source eurostat_sdmx --url https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_a --snapshot-date 2026-02-17 --strict-network --timeout 30` |
| une_rt_a|freq=A|geo=PT|unit=PC_ACT | from-file | 1 | 0 | 0 | 213 | error | series:3feb2dae20867f4bf608324a | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source eurostat_sdmx --from-file docs/etl/sprints/AI-OPS-09/evidence/eurostat-series-samples/une_rt_a_freq_A_geo_PT_unit_PC_ACT.json --snapshot-date 2026-02-17 --timeout 30` |
| une_rt_a|freq=A|geo=PT|unit=PC_ACT | replay | 1 | 0 | 0 | 214 | error | series:3feb2dae20867f4bf608324a | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source eurostat_sdmx --from-file docs/etl/sprints/AI-OPS-09/evidence/eurostat-replay-inputs/une_rt_a_freq_A_geo_PT_unit_PC_ACT/une_rt_a_freq_A_geo_PT_unit_PC_ACT_replay_20260217.json --snapshot-date 2026-02-17 --timeout 30` |

## Replay parity

| series_id | strict_exit | replay_exit | from_file_exit | strict_loaded | replay_loaded | parity | delta_loaded | source_record_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| une_rt_a|freq=A|geo=ES|unit=PC_ACT | 0 | 1 | 1 | 2394 | 0 | DRIFT | 2394 | series:4468f558922332ed237bf17f |
| une_rt_a|freq=A|geo=PT|unit=PC_ACT | 0 | 1 | 1 | 2394 | 0 | DRIFT | 2394 | series:3feb2dae20867f4bf608324a |

## Command logs
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_ES_unit_PC_ACT__from-file.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_ES_unit_PC_ACT__from-file.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_ES_unit_PC_ACT__replay.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_ES_unit_PC_ACT__replay.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_ES_unit_PC_ACT__strict-network.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_ES_unit_PC_ACT__strict-network.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_PT_unit_PC_ACT__from-file.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_PT_unit_PC_ACT__from-file.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_PT_unit_PC_ACT__replay.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_PT_unit_PC_ACT__replay.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_PT_unit_PC_ACT__strict-network.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-logs/une_rt_a_freq_A_geo_PT_unit_PC_ACT__strict-network.stdout.log

## SQL snapshots
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__from-file_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__from-file_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__replay_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__replay_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__strict-network_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_ES_unit_PC_ACT__strict-network_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_PT_unit_PC_ACT__from-file_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_PT_unit_PC_ACT__from-file_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_PT_unit_PC_ACT__replay_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_PT_unit_PC_ACT__replay_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_PT_unit_PC_ACT__strict-network_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/eurostat-apply-sql/une_rt_a_freq_A_geo_PT_unit_PC_ACT__strict-network_source_records_snapshot.csv

## Quarantine / unresolved rows

- rule: quarantine series with repeated failures and continue applying remaining rows
- une_rt_a|freq=A|geo=ES|unit=PC_ACT (from-file): exit=1, reason=Traceback (most recent call last):
  File "/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/politicos_es/connectors/eurostat_indicators.py", line 151, i
- une_rt_a|freq=A|geo=ES|unit=PC_ACT (replay): exit=1, reason=Traceback (most recent call last):
  File "/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/politicos_es/connectors/eurostat_indicators.py", line 151, i
- une_rt_a|freq=A|geo=PT|unit=PC_ACT (from-file): exit=1, reason=Traceback (most recent call last):
  File "/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/politicos_es/connectors/eurostat_indicators.py", line 151, i
- une_rt_a|freq=A|geo=PT|unit=PC_ACT (replay): exit=1, reason=Traceback (most recent call last):
  File "/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/politicos_es/connectors/eurostat_indicators.py", line 151, i
