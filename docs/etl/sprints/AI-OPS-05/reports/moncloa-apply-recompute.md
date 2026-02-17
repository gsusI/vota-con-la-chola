# Moncloa Apply/Recompute AI-OPS-05 (P4)

Date: 2026-02-16
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Objective
Reconfirm Moncloa reproducibility and verify `policy_events` traceability after apply/recompute loop for:
- `moncloa_referencias`
- `moncloa_rss_referencias`

## Commands Run

| command_group | command | stdout | stderr | snapshot |
|---|---|---|---|---|
| strict-network | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --snapshot-date 2026-02-16 --strict-network --timeout 30` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_referencias__strict-network.stdout.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_referencias__strict-network.stderr.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_referencias__strict-network__run_snapshot.csv` |
| from-file | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_referencias__from-file.stdout.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_referencias__from-file.stderr.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_referencias__from-file__run_snapshot.csv` |
| strict-network | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_rss_referencias --snapshot-date 2026-02-16 --strict-network --timeout 30` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_rss_referencias__strict-network.stdout.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_rss_referencias__strict-network.stderr.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_rss_referencias__strict-network__run_snapshot.csv` |
| from-file | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_rss_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_rss_referencias__from-file.stdout.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_rss_referencias__from-file.stderr.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_rss_referencias__from-file__run_snapshot.csv` |
| policy-events recompute | `just etl-backfill-policy-events-moncloa` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_policy_events_backfill.stdout.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/moncloa_policy_events_backfill.stderr.log` | `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_before_policy_events_count.csv` / `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_after_policy_events_count.csv` / `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_before_policy_events_traceability.csv` / `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_after_policy_events_traceability.csv` |

## Before Metrics (captured pre-pass)

Source: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_before_ingestion_runs.csv` and corresponding policy_events snapshots.

- `policy_events` total (Moncloa sources): `28`
- `policy_events` traceability: `total=28 | source_record_pk_not_null=28 | source_id_not_null=28 | source_url_not_null=28`

## Recompute Results

### strict-network outcomes
- `moncloa_referencias` strict-network: `2/2` loaded (success)
- `moncloa_rss_referencias` strict-network: `8/8` loaded (success)

### from-file outcomes
- `moncloa_referencias` from-file: `20/20` loaded (from-dir)
- `moncloa_rss_referencias` from-file: `8/8` loaded (from-dir)

### policy_events backfill
- backfill JSON summary captured in stdout log.
- Source mapped: both Moncloa sources.
- `policy_events_upserted`: `28`
- `policy_events_with_source_url`: `28`
- `policy_events_null_event_date_with_published`: `4`

## After Metrics (captured post-pass)

Source: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/moncloa_after_ingestion_runs.csv` and corresponding policy_events snapshots.

- Acceptance query (`records_loaded` for moncloa_*):

```text
moncloa_rss_referencias|8
moncloa_rss_referencias|8
moncloa_referencias|20
moncloa_referencias|2
moncloa_rss_referencias|8
moncloa_rss_referencias|8
moncloa_referencias|20
moncloa_referencias|2
moncloa_referencias|0
```

- `policy_events` total (Moncloa sources): `28`
- `policy_events` traceability coverage: `28|28|28|28`

## Diff Summary

- `policy_events` count baseline -> after: `28 -> 28` (no delta)
- `source_id LIKE 'moncloa_%'` latest `ingestion_runs` now include fresh strict-network and from-file rows for both sources with non-zero load in all required slots.

## Escalation Check

- Baseline requirement: `policy_events_moncloa >= 28`
- Result: baseline `28`, post-pass `28`; **no decrease**.
- Status: **No escalation** required.
