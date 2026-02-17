# Moncloa Apply/Recompute Report — AI-OPS-04

Date: 2026-02-16  
Repo: `REPO_ROOT/vota-con-la-chola`  
DB: `etl/data/staging/politicos-es.db`

Inputs used:
- `docs/etl/sprints/AI-OPS-04/reports/moncloa-ingest-matrix.md`
- `docs/etl/sprints/AI-OPS-04/reports/moncloa-policy-events-mapping.md`

## 1) Override Batch Prepared

Override artifact:
- `etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216/overrides/moncloa_rss_referencias_override_event_date.json`

Override rationale (deterministic parser miss):
- In Moncloa RSS `tipo15` rows, `event_date_iso` is missing when slug format is `ddmmyy-...`.
- Deterministic rule applied in override: `event_date_iso = published_at_iso[:10]`.

Override rows prepared:
- `4` rows (`source_feed=tipo15`)
- Slugs patched:
  - `030226-rueda-de-prensa-ministros.aspx`
  - `100226-rueda-de-prensa-ministros.aspx`
  - `200126-rueda-de-prensa-ministros.aspx`
  - `270126-rueda-de-prensa-ministros.aspx`

## 2) Re-run Ingest + Mapping (single loop)

Commands executed:

```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_rss_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_rss_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216/overrides/moncloa_rss_referencias_override_event_date.json --snapshot-date 2026-02-16 --timeout 30
python3 scripts/ingestar_politicos_es.py backfill-policy-events-moncloa --db etl/data/staging/politicos-es.db
```

Run evidence (`ingestion_runs` > 153):
- `run_id=154` `moncloa_referencias` `records_loaded=20` (`from-dir`)
- `run_id=155` `moncloa_rss_referencias` `records_loaded=8` (`from-dir`)
- `run_id=156` `moncloa_rss_referencias` `records_loaded=4` (`from-file` override)

Mapping evidence:
- `source_records_seen=29`
- `source_records_mapped=28`
- `source_records_skipped=1` (`referencia:index.aspx` discovery row)
- `policy_events_upserted=28`
- `policy_events_total=28`
- `policy_events_null_event_date_with_published=0`

## 3) Before vs After Metrics

### A) Loaded rows (`source_records`)

| metric | before | after |
|---|---:|---:|
| `moncloa_referencias` rows | 3 | 21 |
| `moncloa_rss_referencias` rows | 4 | 8 |
| total moncloa rows | 7 | 29 |

### B) Parser nulls (`source_records.raw_payload`)

| source_id | metric | before | after |
|---|---|---:|---:|
| `moncloa_referencias` | `event_date_iso_nulls` | 1/3 | 1/21 |
| `moncloa_referencias` | `published_at_iso_nulls` | 1/3 | 1/21 |
| `moncloa_referencias` | `summary_text_nulls` | 2/3 | 2/21 |
| `moncloa_rss_referencias` | `event_date_iso_nulls` | 0/4 | 0/8 |
| `moncloa_rss_referencias` | `published_at_iso_nulls` | 0/4 | 0/8 |

Parser-miss proof at payload level (`before` run payload vs `after` override payload):
- `before` file: `etl/data/raw/moncloa_rss_referencias/2026/02/16/moncloa_rss_referencias_20260216T145318Z.json`
  - total rows: `8`
  - `event_date_iso` nulls: `4`
  - `tipo15` rows: `4`, all `4/4` missing `event_date_iso`
- `after` override file: `etl/data/raw/moncloa_rss_referencias/2026/02/16/moncloa_rss_referencias_20260216T145326Z.json`
  - override rows: `4`
  - `event_date_iso` nulls: `0`

### C) `policy_events` coverage

| source_id | metric | before | after |
|---|---|---:|---:|
| `moncloa_referencias` | `policy_events_total` | 2 | 20 |
| `moncloa_referencias` | `null_event_date` | 0 | 0 |
| `moncloa_referencias` | `null_source_url` | 0 | 0 |
| `moncloa_rss_referencias` | `policy_events_total` | 4 | 8 |
| `moncloa_rss_referencias` | `null_event_date` | 0 | 0 |
| `moncloa_rss_referencias` | `null_source_url` | 0 | 0 |

Combined `policy_events` (moncloa sources):
- `before`: `6`
- `after`: `28`

## 4) Escalation Rule Check

Rule: escalate to L2 if override volume exceeds `20%` of rows.

Computed override volume:
- override rows: `4`
- moncloa rows after apply: `29`
- override volume: `4/29 = 13.79%`

Decision:
- **No escalation required** (below 20%).

## Result

- Override/recompute loop executed successfully.
- Deterministic RSS parser miss (`tipo15 event_date_iso`) patched via override batch.
- Moncloa `policy_events` re-materialized and expanded from `6` to `28` with `source_url` coverage preserved.
