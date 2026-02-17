# AEMET apply/recompute report
Timestamp: 2026-02-17T08:48:22.846148Z
DB: etl/data/staging/politicos-es.db
Snapshot: 2026-02-17

## Executed matrix rows
| series_id | station_id | variable | mode | exit_code | seen | loaded | status | run_id | source_records |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| station:3195:var:tmed | 3195 | tmed | strict-network | 1 | 0 | 0 | error | 219 | 2 |
| station:3195:var:tmed | 3195 | tmed | replay | 1 | 0 | 0 | error | 220 | 2 |
| station:0076:var:prec | 0076 | prec | strict-network | 1 | 0 | 0 | error | 221 | 2 |
| station:0076:var:prec | 0076 | prec | replay | 1 | 0 | 0 | error | 222 | 2 |

| series_id | strict_exit | replay_exit | strict_loaded | replay_loaded | parity | delta_loaded |
| --- | --- | --- | --- | --- | --- | --- |
| station:0076:var:prec | 1 | 1 | 0 | 0 | PASS | 0 |
| station:3195:var:tmed | 1 | 1 | 0 | 0 | PASS | 0 |

## Evidence paths
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_0076_prec__replay.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_0076_prec__replay.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_0076_prec__strict-network.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_0076_prec__strict-network.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_3195_tmed__replay.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_3195_tmed__replay.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_3195_tmed__strict-network.stderr.log
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-logs/station_3195_tmed__strict-network.stdout.log
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-sql/station_0076_prec__replay_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-sql/station_0076_prec__replay_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-sql/station_0076_prec__strict-network_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-sql/station_0076_prec__strict-network_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-sql/station_3195_tmed__replay_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-sql/station_3195_tmed__replay_source_records_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-sql/station_3195_tmed__strict-network_run_snapshot.csv
- docs/etl/sprints/AI-OPS-09/evidence/aemet-apply-sql/station_3195_tmed__strict-network_source_records_snapshot.csv

## Quarantine / unresolved
Quarantine rule: if token/quota/network issues prevent completion, retain partial evidence and do not mark DONE.
- station:3195:var:tmed (strict-network): exit=1 reason=Traceback (most recent call last):
- station:3195:var:tmed (replay): exit=1 reason=Traceback (most recent call last):
- station:0076:var:prec (strict-network): exit=1 reason=Traceback (most recent call last):
- station:0076:var:prec (replay): exit=1 reason=Traceback (most recent call last):
