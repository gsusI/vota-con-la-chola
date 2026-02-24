# AI-OPS-24 Closeout

Status: PARTIAL (Congreso DONE, Senado PARTIAL+BLOCKED, coverage improved)

## Gates
- G1 Congreso coverage (linked-to-votes): PASS
  - `initiatives_linked_to_votes_with_downloaded_docs=104/104 (100%)`
  - Evidence: `docs/etl/sprints/AI-OPS-24/exports/quality_initiatives_2026-02-18_final2.json`
  - Missing URLs: `docs/etl/sprints/AI-OPS-24/exports/congreso_missing_doc_urls_2026-02-18.txt` (0)
- G2 Senado coverage or blocker: PASS (partial progress + blocker documented)
  - `initiatives_linked_to_votes_with_downloaded_docs=235/647 (36.32%)`
  - Failure mode: partial bypass works for a subset, but stable runs still hit `HTTP 403/500` on `detalleiniciativa`/`ficopendataservlet`.
  - Evidence (partial success): `docs/etl/sprints/AI-OPS-24/evidence/senado_initdocs_playwright_resume_run_2026-02-18.log`
  - Evidence (remaining blocker): `docs/etl/sprints/AI-OPS-24/evidence/senado_initdocs_prioritized_auto_2026-02-18.log`
  - Missing/blocked URLs (top 500): `docs/etl/sprints/AI-OPS-24/exports/senado_missing_doc_urls_403_2026-02-18.txt`
  - Unblock runbook: `docs/etl/sprints/AI-OPS-24/reports/senado-cookie-capture-kit.md`
- G3 No retry loops on permanent blocks: PASS
  - Mechanism: `document_fetches` caches `403/404` and downloader skips them by default.
  - Evidence: `docs/etl/sprints/AI-OPS-24/evidence/senado_initdocs_dryrun_2026-02-18.txt` shows `skipped_forbidden=100`.
- G4 Visible UI delta: PASS
  - Vote summaries now include `initiative.documents` (counts + URLs + downloaded flag) for auditability.
  - Implementation: `scripts/graph_ui_server.py`

## Evidence
- See `docs/etl/sprints/AI-OPS-24/evidence/` and `docs/etl/sprints/AI-OPS-24/exports/`.

## Commands Run (2026-02-18)
- Backfill initiative link columns (no-op once fixed):  
  `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-links --db etl/data/staging/politicos-es.db --source-ids congreso_iniciativas,senado_iniciativas`
- Download Congreso initiative documents (auto):  
  `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids congreso_iniciativas --auto --max-loops 50`
- Probe Senado with forced retry (expected 403):  
  `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --limit-initiatives 10 --max-docs-per-initiative 1 --retry-forbidden`
- Senado Playwright pass with persisted profile (partial success):  
  `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --limit-initiatives 200 --max-docs-per-initiative 6 --retry-forbidden --playwright-user-data-dir etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile --playwright-headless --timeout 25`
- Senado breadth pass (still blocked for remaining URLs):  
  `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --limit-initiatives 2000 --max-docs-per-initiative 1 --retry-forbidden --playwright-user-data-dir etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile --playwright-headless --timeout 25`
- Senado prioritized auto pass (new queue ordering + skip forbidden):  
  `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --auto --max-loops 12 --limit-initiatives 300 --max-docs-per-initiative 1 --playwright-user-data-dir etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile --playwright-headless --timeout 25`
- Export KPIs:  
  `python3 scripts/ingestar_parlamentario_es.py quality-report --db etl/data/staging/politicos-es.db --include-initiatives --initiative-source-ids congreso_iniciativas,senado_iniciativas --json-out docs/etl/sprints/AI-OPS-24/exports/quality_initiatives_2026-02-18_final2.json`
