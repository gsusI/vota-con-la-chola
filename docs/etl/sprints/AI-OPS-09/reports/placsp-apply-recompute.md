# AI-OPS-09 PLACSP apply/recompute report

## Scope
- Deterministic matrix source: `docs/etl/sprints/AI-OPS-09/exports/placsp_ingest_matrix.csv`
- Evidence logs: `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/`
- Evidence SQL snapshots: `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-sql/`

## Command matrix execution (strict-network / from-file / replay)

|source_id|mode|command|exit_code|before_records|after_records|delta_records|run_records_seen|run_records_loaded|run_status|run_id|anti_bot|evidence_stdout|evidence_stderr|notes|
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|
|placsp_sindicacion|strict-network|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_sindicacion --snapshot-date 2026-02-17 --strict-network --timeout 30|120|109|109|0|106|106|ok|192|FALSE|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__strict-network.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__strict-network.stderr.log|strict-network execution hit client timeout in strict guard path (`TimeoutError`) and returned no usable records load delta|
|placsp_sindicacion|from-file|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_sindicacion --from-file etl/data/raw/samples/placsp_sindicacion_sample.xml --snapshot-date 2026-02-17 --timeout 30|0|109|109|0|3|3|ok|193|FALSE|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__from-file.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__from-file.stderr.log|deterministic sample ingest completed successfully|
|placsp_sindicacion|replay|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_sindicacion --from-file docs/etl/sprints/AI-OPS-09/evidence/placsp-replay-inputs/placsp_sindicacion/placsp_sindicacion_replay_20260217.xml --snapshot-date 2026-02-17 --timeout 30|1|109|109|0|0|0|error|194|FALSE|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__replay.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__replay.stderr.log|replay fixture is empty (`wc -c = 0`) and XML parse rejects empty payload with `payload_sig=e3b0...`|
|placsp_autonomico|strict-network|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_autonomico --snapshot-date 2026-02-17 --strict-network --timeout 30|0|0|106|106|106|106|ok|195|FALSE|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__strict-network.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__strict-network.stderr.log|strict-network ingest is reproducibly successful, non-zero `records_loaded`|
|placsp_autonomico|from-file|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_autonomico --from-file etl/data/raw/samples/placsp_autonomico_sample.xml --snapshot-date 2026-02-17 --timeout 30|0|106|108|2|2|2|ok|196|FALSE|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__from-file.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__from-file.stderr.log|deterministic sample ingest completed successfully, source produced non-zero replay candidates|
|placsp_autonomico|replay|python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_autonomico --from-file docs/etl/sprints/AI-OPS-09/evidence/placsp-replay-inputs/placsp_autonomico/placsp_autonomico_replay_20260217.xml --snapshot-date 2026-02-17 --timeout 30|1|108|108|0|0|0|error|197|FALSE|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__replay.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__replay.stderr.log|replay fixture is empty (`wc -c = 0`) and XML parse rejects empty payload with `payload_sig=e3b0...`|

## Replay parity checks

|source_id|strict_delta|from_file_delta|replay_delta|replay_parity|
|-|-|-|-|-|
|placsp_sindicacion|0|0|0|FAIL (replay exit_code=1)
|placsp_autonomico|106|2|0|FAIL (replay exit_code=1)

## Escalation / blockers

|source_id|mode|anti_bot|status_code_hint|stdout_log|stderr_log|
|-|-|-|-|-|-|
|placsp_sindicacion|strict-network|FALSE|TimeoutError|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__strict-network.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__strict-network.stderr.log|
|placsp_sindicacion|replay|FALSE|ParseError no element found|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__replay.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_sindicacion__replay.stderr.log|
|placsp_autonomico|replay|FALSE|ParseError no element found|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__replay.stdout.log|docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/placsp_autonomico__replay.stderr.log|

## Evidence outputs written

- `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-logs/`
- `docs/etl/sprints/AI-OPS-09/evidence/placsp-apply-sql/`
