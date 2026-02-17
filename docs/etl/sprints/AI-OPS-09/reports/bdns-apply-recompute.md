# AI-OPS-09 BDNS apply/recompute report

## Command matrix execution (strict-network / from-file / replay)

|source_id|mode|command|exit_code|before_records|after_records|delta_records|run_records_seen|run_records_loaded|run_status|run_id|evidence_stdout|evidence_stderr|notes|
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|
|bdns_api_subvenciones|strict-network|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_api_subvenciones --snapshot-date 2026-02-17 --strict-network --timeout 30|1|3|3|0|0|0|error|199|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__strict-network.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__strict-network.stderr.log|strict-network returned anti-HTML payload (`Respuesta HTML inesperada para BDNS feed`, payload_sig=0401a40b...) |
|bdns_api_subvenciones|from-file|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_api_subvenciones --from-file etl/data/raw/samples/bdns_api_subvenciones_sample.json --snapshot-date 2026-02-17 --timeout 30|0|3|3|0|3|3|ok|200|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__from-file.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__from-file.stderr.log|deterministic sample ingest completed successfully|
|bdns_api_subvenciones|replay|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_api_subvenciones --from-file docs/etl/sprints/AI-OPS-09/evidence/bdns-replay-inputs/bdns_api_subvenciones/bdns_api_subvenciones_replay_20260217.json --snapshot-date 2026-02-17 --timeout 30|1|3|3|0|0|0|error|201|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__replay.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__replay.stderr.log|input file missing for replay fixture |
|bdns_autonomico|strict-network|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_autonomico --snapshot-date 2026-02-17 --strict-network --timeout 30|1|0|0|0|0|0|error|202|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__strict-network.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__strict-network.stderr.log|strict-network returned anti-HTML payload (`Respuesta HTML inesperada para BDNS feed`, payload_sig=0401a40b...) |
|bdns_autonomico|from-file|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_autonomico --from-file etl/data/raw/samples/bdns_autonomico_sample.json --snapshot-date 2026-02-17 --timeout 30|0|0|2|2|2|2|ok|203|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__from-file.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__from-file.stderr.log|deterministic sample ingest completed successfully|
|bdns_autonomico|replay|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_autonomico --from-file docs/etl/sprints/AI-OPS-09/evidence/bdns-replay-inputs/bdns_autonomico/bdns_autonomico_replay_20260217.json --snapshot-date 2026-02-17 --timeout 30|1|2|2|0|0|0|error|204|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__replay.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__replay.stderr.log|input file missing for replay fixture |

## Replay parity checks

|source_id|strict_delta|from_file_delta|replay_delta|replay_parity|
|-|-|-|-|-|
|bdns_api_subvenciones|0|0|0|FAIL (replay exit_code=1; blocker: replay fixture missing)|
|bdns_autonomico|0|2|0|FAIL (replay exit_code=1; blocker: replay fixture missing)|

## Escalation / contract blockers

|source_id|mode|anti_bot|status_code_hint|stdout_log|stderr_log|
|-|-|-|-|-|-|
|bdns_api_subvenciones|strict-network|TRUE|`Respuesta HTML inesperada para BDNS feed`|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__strict-network.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__strict-network.stderr.log|
|bdns_autonomico|strict-network|TRUE|`Respuesta HTML inesperada para BDNS feed`|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__strict-network.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__strict-network.stderr.log|
|bdns_api_subvenciones|replay|FALSE|`FileNotFoundError` replay file not found|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__replay.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__replay.stderr.log|
|bdns_autonomico|replay|FALSE|`FileNotFoundError` replay file not found|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__replay.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__replay.stderr.log|

## Evidence outputs written

- matrix logs: `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/`
- SQL snapshots: `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-sql/`
