# Initiative Doc Fetch-Status Backfill (2026-02-22)

## Goal
Restore `document_fetches` traceability for historical initiative docs that were already downloaded and linked (`parl_initiative_documents + text_documents`) but still had no fetch-status row.

## Implementation
New utility:
- `scripts/backfill_initiative_doc_fetch_status.py`

Capabilities:
- Reconstruct `document_fetches` success rows (`fetched_ok=1`, `last_http_status=200`) from already materialized docs.
- Optional scope by initiative source (`--initiative-source-id`).
- Dry-run mode for deterministic planning.

## Run snapshot
Command:
```bash
python3 scripts/backfill_initiative_doc_fetch_status.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs
```

Observed result:
- `candidate_urls=157` (representing `candidate_refs_total=205` doc links)
- `inserted_or_would_insert=157`
- Coverage before: `8761/8966` doc links with fetch-status (`missing=205`)
- Coverage after: `8966/8966` (`missing=0`)

## Evidence
- Post-state KPI snapshot:
  - `docs/etl/sprints/AI-OPS-27/evidence/initdoc_fetch_status_post_20260222T102357Z.json`
- Latest bounded Senate retry after normalization:
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_tail_retry_post_fetchstatus_20260222T102357Z.json`

## KPI impact
- Congreso initiative docs now report complete fetch traceability:
  - `812/812` links with fetch status (`100%`).
- Senate remains:
  - `8154/8273` fetched (`98.56%`), tail `119` now all `HTTP 404` in latest retry.
- Combined initiative-doc progress:
  - `8966/9085` fetched (`98.69%`).

## Why this matters
- Removes false “missing” noise caused by absent historical fetch metadata.
- Keeps blocker analysis focused on the real unresolved Senate tail (`119` URLs), not on bookkeeping gaps.
