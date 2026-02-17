# Moncloa Ingest Matrix — AI-OPS-04

Date: 2026-02-16
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`
DB used for matrix: `etl/data/staging/moncloa-aiops04-matrix-20260216.db`
Batch replay input: `etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216`
Depends on: `4`
Parallel group: `P4`

## Scope
Run ingestion matrix for new Moncloa source IDs:
- `moncloa_referencias`
- `moncloa_rss_referencias`

Modes executed:
- `strict-network` (live fetch, guardrails enabled)
- `from-file` (replay from prepared batch dir)

## Commands Executed

```bash
python3 scripts/ingestar_politicos_es.py init-db --db etl/data/staging/moncloa-aiops04-matrix-20260216.db

python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/moncloa-aiops04-matrix-20260216.db --source moncloa_referencias --snapshot-date 2026-02-16 --strict-network --timeout 30
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/moncloa-aiops04-matrix-20260216.db --source moncloa_rss_referencias --snapshot-date 2026-02-16 --strict-network --timeout 30

python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/moncloa-aiops04-matrix-20260216.db --source moncloa_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/moncloa-aiops04-matrix-20260216.db --source moncloa_rss_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30

# repeatability pass
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/moncloa-aiops04-matrix-20260216.db --source moncloa_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/moncloa-aiops04-matrix-20260216.db --source moncloa_rss_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30
```

## Run Matrix (per run)

| run_id | source_id | mode | status | records_seen | records_loaded | duration_s | evidence |
|---:|---|---|---|---:|---:|---:|---|
| 1 | `moncloa_referencias` | `strict-network` | `error` | 0 | 0 | 3.0 | `<urlopen error [Errno 8] nodename nor servname provided, or not known>` |
| 2 | `moncloa_rss_referencias` | `strict-network` | `error` | 0 | 0 | 6.0 | `No se pudo extraer ningun item RSS de Moncloa` |
| 3 | `moncloa_referencias` | `from-file` | `ok` | 20 | 20 | 0.0 | `Ingesta completada ... (from-dir)` |
| 4 | `moncloa_rss_referencias` | `from-file` | `ok` | 8 | 8 | 0.0 | `Ingesta completada ... (from-dir)` |
| 5 | `moncloa_referencias` | `from-file` | `ok` | 20 | 20 | 0.0 | repeatability pass |
| 6 | `moncloa_rss_referencias` | `from-file` | `ok` | 8 | 8 | 0.0 | repeatability pass |

## Aggregated Comparison

| mode | runs | ok_runs | error_runs | failure_rate | total_seen | total_loaded | avg records_loaded/run |
|---|---:|---:|---:|---:|---:|---:|---:|
| `strict-network` | 2 | 0 | 2 | 100.0% | 0 | 0 | 0.0 |
| `from-file` | 4 | 4 | 0 | 0.0% | 56 | 56 | 14.0 |

## Throughput / Payload Evidence

From `run_fetches` and `raw_fetches` (from-file runs):

| source_id | mode | payload bytes | content_sha256 | unique payloads in raw_fetches |
|---|---|---:|---|---:|
| `moncloa_referencias` | `from-file` | 21234 | `ab08b7dc09a46c890f055e95fdeac5e7d716a5023f8792f19ce440a239271ddf` | 1 |
| `moncloa_rss_referencias` | `from-file` | 13262 | `ab34b1ced7919300f9a785f07a60f475b084ad89cf401367a4003f9fff50a1b0` | 1 |

Interpretation: replay produced byte-identical payloads across both passes (`repeatability` at payload level).

## Repeatability Check

`from-file` pass1 vs pass2:

| source_id | runs_ok | min records_loaded | max records_loaded | repeatability |
|---|---:|---:|---:|---|
| `moncloa_referencias` | 2 | 20 | 20 | `yes` |
| `moncloa_rss_referencias` | 2 | 8 | 8 | `yes` |

Additional idempotence evidence in DB final state:
- `source_records` count = `20` for `moncloa_referencias`
- `source_records` count = `8` for `moncloa_rss_referencias`

These totals match single-pass unique records, despite two replay passes.

## Blocker Decision (escalation_rule)

Condition check:
- `strict-network` failed
- `from-file` succeeded

Result: **BLOCKER CONFIRMED**.

Blocker statement for sprint tracking:
- Live Moncloa network ingest is blocked in this environment (DNS/network resolution and zero-item RSS outcome under strict-network), while deterministic replay from captured batch is healthy and repeatable.
- Continue sprint with `from-file`/captured artifacts for implementation and QA gates until network path is restored.

## Acceptance Query

```bash
rg -n "strict-network|from-file|records_loaded|repeatability" docs/etl/sprints/AI-OPS-04/reports/moncloa-ingest-matrix.md
```
