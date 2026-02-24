# Senate Initiative Docs Retry Summary (2026-02-20)

Run ID: `senado_retry_20260220T000000Z`
Date (UTC): `2026-02-20T00:00:00Z`

## Commanded Process

- Executed `scripts/ingestar_parlamentario_es.py backfill-initiative-documents` for `senado_iniciativas` using existing built-in options:
  - no profile
  - Playwright session profile
  - cookie file
- Each run: `--include-unlinked --max-docs-per-initiative 1 --limit-initiatives 12 --retry-forbidden`.

## Evidence Artifacts

- `docs/etl/sprints/AI-OPS-26/evidence/senado_retry_noprofile_20260220T0000.json`
- `docs/etl/sprints/AI-OPS-26/evidence/senado_retry_playwright_20260220T0000.json`
- `docs/etl/sprints/AI-OPS-26/evidence/senado_retry_cookiefile_20260220T0000.json`
- `docs/etl/sprints/AI-OPS-26/reports/senado-vpn-retry-20260220.md`

## Delta

All three attempts returned:

- `candidate_urls: 24`
- `initiatives_seen: 12`
- `fetched_ok: 0`
- `text_documents_upserted: 0`
- `initiative_documents_upserted: 24`

## Failure Pattern

- no-profile: all failures `HTTP 403`.
- Playwright profile: mostly `HTTP 500`, some `HTTP 403`.
- cookie-file: all `HTTP 500`.

## Outcome

No deterministic progress on Senate initiative documents at the configured queue depth. The blocker behavior persists.
