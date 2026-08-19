# Senado Initiative Docs Retry Report (2026-02-20)

## Objective
Process Senate initiative doc queue via the existing `backfill-initiative-documents` process after the VPN session change, to confirm whether blocking persists and update the evidence trail for future collaborators.

## Commands Executed

1. Baseline queue check (no browser context)
```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents   --db etl/data/staging/politicos-es.db   --initiative-source-ids senado_iniciativas   --include-unlinked   --max-docs-per-initiative 1   --limit-initiatives 12   --retry-forbidden   --timeout 10
```
Evidence: `docs/etl/sprints/AI-OPS-26/evidence/senado_retry_noprofile_20260220T0000.json`

2. Browser profile rerun (Playwright)
```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents   --db etl/data/staging/politicos-es.db   --initiative-source-ids senado_iniciativas   --include-unlinked   --max-docs-per-initiative 1   --limit-initiatives 12   --retry-forbidden   --timeout 8   --playwright-user-data-dir etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z_profile   --playwright-headless   --sleep-seconds 0   --sleep-jitter-seconds 0
```
Evidence: `docs/etl/sprints/AI-OPS-26/evidence/senado_retry_playwright_20260220T0000.json`

3. Cookie-header rerun
```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents   --db etl/data/staging/politicos-es.db   --initiative-source-ids senado_iniciativas   --include-unlinked   --max-docs-per-initiative 1   --limit-initiatives 12   --retry-forbidden   --timeout 8   --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json   --sleep-seconds 0   --sleep-jitter-seconds 0
```
Evidence: `docs/etl/sprints/AI-OPS-26/evidence/senado_retry_cookiefile_20260220T0000.json`

## Results Summary

All three runs executed cleanly, and all are `fetched_ok=0` for a sample batch.

- `candidate_urls=24` and `initiatives_seen=12` in each pass.
- No `text_documents_upserted` in any pass.
- Failure pattern remained blocking/upstream errors:
  - no-profile: all `HTTP 403`.
  - Playwright profile: all `HTTP 500` (mostly) and some `HTTP 403`.
  - cookie-file: all `HTTP 500`.

This confirms that VPN/browser-session variance did not restore deterministic Senate initiative document access in this environment during this window.

## DB Snapshot After These Checks

From `etl/data/staging/politicos-es.db` (checked post-run):
- `congreso_iniciativas`: `399/812` initiative docs downloaded.
- `senado_iniciativas`: `1422/7713` initiatives with doc links, and `235/647` of Senate linked-to-vote initiatives still have docs (`1:1` baseline as tracked in prior quality run).
- `parl_initiative_docs` fetch table shows mixed historical statuses on Senate queue rows, heavily dominated by `403/500` for Senate URLs (e.g. latest `legis9/610` sample set: `(200=1131,403=1517,500=777, null=269)`).

## Operational Takeaways

- The project already has a ready command path; no custom scraper is required.
- On this date, Senate docs are still effectively blocked by endpoint behavior (`403/500`) under both non-browser and browser-assisted modes.
- Next step to move forward is to acquire a fresh official-access lever (new profile/cookie + alternate official endpoint) before resuming high-volume retry.

## Next Actions

- Re-run with a fresh browser session immediately after interactive human-authenticated verification if available.
- Add a `--playwright-user-data-dir` capture + timestamped follow-up proof under `etl/data/raw/manual/` and rerun bounded `--auto` chunks with evidence checkpoints.
- If failures remain `403/500`, log a new blocker incident window in `docs/etl/name-and-shame-access-blockers.md` with this run evidence.
