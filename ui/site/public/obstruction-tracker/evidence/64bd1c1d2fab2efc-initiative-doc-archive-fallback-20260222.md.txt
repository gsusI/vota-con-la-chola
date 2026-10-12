# Initiative Doc Archive Fallback (2026-02-22)

## Scope
- Source: `senado_iniciativas`
- Target tail: doc links still missing with historical `HTTP 404`
- DB: `etl/data/staging/politicos-es.db`

## What changed
- Added opt-in archive fallback support to initiative-doc downloader:
  - CLI flags: `--archive-fallback`, `--archive-timeout`
  - Backfill behavior:
    - For hard-failed `404` URLs (already in `document_fetches`), it runs archive lookup first.
    - On direct fetch `404`, it also attempts archive lookup before final failure.
  - Traceability:
    - `source_records.raw_payload` now stores `fetch_method` and, when applicable, `fetched_from_url`/`archive_timestamp`.

## Run executed
```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --include-unlinked \
  --archive-fallback \
  --archive-timeout 12 \
  --limit-initiatives 5000 \
  --max-docs-per-initiative 1 \
  --timeout 10 \
  --sleep-seconds 0 \
  --sleep-jitter-seconds 0
```

Evidence JSON:
- `docs/etl/sprints/AI-OPS-27/evidence/initdoc_archive_sweep_20260222T135005Z.json`

## Result
- `candidate_urls=119`
- `archive_first_urls=119`
- `archive_lookup_attempted=119`
- `archive_hits=0`
- `archive_fetched_ok=0`
- `fetched_ok=0`

All remaining URLs in this tail returned archive miss (`archive fallback: no snapshot candidates`).

## Post-checkpoint
Post-run status snapshot:
- `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_after_archive_20260222T135622Z.json`

State after run:
- Senate docs downloaded: `8154/8273` (`98.56%`)
- Missing remains: `119` (status bucket still `404`)
- Updated actionable URL packet: `docs/etl/sprints/AI-OPS-27/exports/senado_tail_missing_urls_after_archive_20260222.csv`
- Subsequent triage (INI/detail fallback) refined this tail to `115` likely-not-expected + `4` actionable:
  - `docs/etl/sprints/AI-OPS-27/reports/senado-tail-triage-20260222.md`
  - `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_enhanced_detailfallback_20260222T140646Z.json`

## Operational conclusion
- Archive fallback is now available and reproducible (shipped), but for this specific Senate tail it did not recover documents because no archive snapshots were returned.
- Keep bounded retry cadence and maintain OPEN blocker/escalation until an alternate official mirror or upstream URL restoration appears.
