# Money policy-events recompute (AI-OPS-09)

## Scope
Recompute canonical money-domain `policy_events` for PLACSP/BDNS source records after ingestion from T8/T16/T17 and produce reproducible SQL artifacts.

## Commands run
1. Deterministic backfill:
   - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-policy-events-money --db etl/data/staging/politicos-es.db --source-ids placsp_sindicacion placsp_autonomico bdns_api_subvenciones bdns_autonomico"`
2. Command log stored at:
   - `docs/etl/sprints/AI-OPS-09/evidence/money-policy-events-sql/backfill-policy-events-money.log`

## Before snapshot (pre-recompute)
- `before_counts.csv`
  - `source_id,count`
  - `bdns_subvenciones,3`
  - `placsp_contratacion,3`
- `before_trace_counts.csv`
  - `source_id,row_count,with_source_record_pk,with_source_url`
  - `bdns_subvenciones,3,3,3`
  - `placsp_contratacion,3,3,3`

## Command output (summary)
```json
{
  "sources": [
    "placsp_sindicacion",
    "placsp_autonomico",
    "bdns_api_subvenciones",
    "bdns_autonomico"
  ],
  "source_records_seen": 222,
  "source_records_mapped": 222,
  "source_records_skipped": 0,
  "policy_events_upserted": 222,
  "skips": [],
  "policy_events_total": 222,
  "policy_events_with_source_url": 222,
  "policy_events_with_source_record_pk": 222,
  "policy_events_by_source": {
    "bdns_subvenciones": 5,
    "placsp_contratacion": 217
  }
}
```

## After snapshot (post-recompute)
- `after_counts.csv`
  - `source_id,count`
  - `bdns_subvenciones,5`
  - `placsp_contratacion,217`
- `after_trace_counts.csv`
  - `source_id,row_count,with_source_record_pk,with_source_url`
  - `bdns_subvenciones,5,5,5`
  - `placsp_contratacion,217,217,217`

## Traceability checks
- `source_record_pk` is populated for all recomputed money policy events (`with_source_record_pk` equals `row_count` for both source IDs).
- `source_url` is populated for all recomputed money policy events (`with_source_url` equals `row_count` for both source IDs).
- Detailed examples are in:
  - `before_trace_sample.csv`
  - `after_trace_sample.csv`

## Before/after counts (delta)
- `placsp_contratacion`: `3 -> 217` (`+214`)
- `bdns_subvenciones`: `3 -> 5` (`+2`)

## Low-confidence / uncertainty handling
- No low-confidence mapping signals were detected in command output (`skips` is empty).
- No rows were flagged `UNRESOLVED` during this recompute.
- If downstream policy consumers require explicit uncertainty tags, map them in a follow-up policy normalization pass (none currently emitted by `backfill-policy-events-money`).

## Artifact inventory
- `docs/etl/sprints/AI-OPS-09/evidence/money-policy-events-sql/before_counts.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/money-policy-events-sql/after_counts.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/money-policy-events-sql/before_trace_counts.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/money-policy-events-sql/after_trace_counts.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/money-policy-events-sql/before_trace_sample.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/money-policy-events-sql/after_trace_sample.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/money-policy-events-sql/backfill-policy-events-money.log`
