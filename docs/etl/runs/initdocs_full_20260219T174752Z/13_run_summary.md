# Initiative Documents Full Run Summary

Run ID:
- `initdocs_full_20260219T174752Z`

Date (UTC):
- `2026-02-19`

Outcome:
- `PARTIAL_BLOCKED`
- Congreso bulk download succeeded.
- Senado remained blocked in this environment (profile-backed attempts yielded zero successful fetches in chunked retries).

## What was executed

1. Baseline quality snapshot and initiative-link backfill.
2. Congreso micro passes (initial) plus one full bulk pass.
3. Senado profile-backed attempts:
   - one oversized pass was interrupted (would take too long for a single page of candidates),
   - replaced with fast chunked passes (`limit-initiatives=120`, stop after 3 no-progress passes).
4. Post-run quality report + missing URL exports + hard counts.

## KPI delta (before -> after)

Source: `00_quality_before.json` vs `09_quality_after.json`.

- `initiatives_with_downloaded_docs`: `340 -> 634` (`+294`)
- `initiatives_with_doc_links`: `956 -> 1666` (`+710`)
- `initiatives_linked_to_votes_with_downloaded_docs`: `339 -> 339` (`+0`)

By source (`initiatives_with_downloaded_docs`):
- `congreso_iniciativas`: `105 -> 399` (`+294`)
- `senado_iniciativas`: `235 -> 235` (`+0`)

By source (`initiatives_with_doc_links`):
- `congreso_iniciativas`: `109 -> 399` (`+290`)
- `senado_iniciativas`: `847 -> 1267` (`+420`)

## Final counts

Source: `12_counts.csv` and DB checks.

- `downloaded_documents` (`text_documents.source_id='parl_initiative_docs'`): `1041`
- `initiatives_with_downloaded_docs` (all initiative sources): `634`
- By source:
  - `congreso_iniciativas`: `399/429`
  - `senado_iniciativas`: `235/3607`

Linked-vote downloaded-doc coverage (from `09_quality_after.json`):
- `congreso_iniciativas`: `104/104` (`1.0000`)
- `senado_iniciativas`: `235/647` (`0.3632`)

## Senado blocker evidence in this run

Chunked summary: `08_senado_chunk_summary.json`

- Pass 01: `candidate_urls=277`, `fetched_ok=0`, `failures=30`
- Pass 02: `candidate_urls=341`, `fetched_ok=0`, `failures=30`
- Pass 03: `candidate_urls=288`, `fetched_ok=0`, `failures=30`
- Stop reason: `no_progress_3`

Missing unresolved doc URLs export:
- `10_missing_all.csv`: `2913` rows (all currently Senado)
- `11_missing_senado_403.csv`: `2558` rows

## Artifacts

- `docs/etl/runs/initdocs_full_20260219T174752Z/06_congreso_auto_full.json`
- `docs/etl/runs/initdocs_full_20260219T174752Z/08_senado_chunk_summary.json`
- `docs/etl/runs/initdocs_full_20260219T174752Z/09_quality_after.json`
- `docs/etl/runs/initdocs_full_20260219T174752Z/10_missing_all.csv`
- `docs/etl/runs/initdocs_full_20260219T174752Z/11_missing_senado_403.csv`
- `docs/etl/runs/initdocs_full_20260219T174752Z/12_counts.csv`
