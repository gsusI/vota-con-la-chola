# Senado Tail Status (2026-02-22)

## Scope
- Source: `senado_iniciativas`
- Artifact model: `parl_initiative_documents` + `text_documents(source_id='parl_initiative_docs')`

## Current checkpoint
- DB: `etl/data/staging/politicos-es.db`
- Coverage: `8204/8323` (`98.57%`)
- Missing: `119`
- Linked-to-votes initiatives with downloaded docs: `647/647` (`100%`)
- Breakdown:
  - `bocg`: `3885/4004` (missing `119`)
  - `ds`: `4319/4319` (complete)

## What changed in this push window
- Additional recovered docs during bounded retries before plateau:
  - `+65` in `docs/etl/runs/senado_postfix_bounded12_20260221T133419Z/`
- Subsequent bounded retries stayed at `0` on remaining tail:
  - `docs/etl/runs/senado_postfix_bounded13_20260221T133628Z/`
  - `docs/etl/runs/senado_postfix_bounded14_20260221T134124Z/`
  - `docs/etl/runs/senado_postfix_bounded15_20260221T134423Z/`
  - `docs/etl/runs/senado_postfix_bounded16_20260221T135423Z/`
  - `docs/etl/runs/senado_postfix_bounded17_20260221T183415Z/`
- Fresh bounded retry after fetch-status normalization (still `0` recovered):
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_tail_retry_post_fetchstatus_20260222T102357Z.json`
- Real daemon pass with anti-stall guards (still `0` recovered, exits cleanly):
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_tail_daemon_real_20260222T103548Z/_stop_summary.json`

## Tail diagnostics
- Remaining URL pattern is concentrated in:
  - `http://www.senado.es/legis10/expedientes/610/enmiendas/global_enmiendas_vetos_10_610*.xml`
  - Small remainder in similar `global_enmiendas_vetos` XML URLs (legis12/14/15)
- Active behavior now:
  - Retry pipeline: `fetched_ok=0` on tail
  - Playwright profile dry-run: `fetched_ok=0` on tail
  - Direct probe sample (`curl`): `4/4` returned `HTTP 404`
  - Wayback lookup sample: no available snapshots
- Post-retry `document_fetches` distribution for tail: `HTTP 404 = 119`
- Triage split (enhanced status):
  - `119` links are `likely_not_expected_redundant_global_url` (the same initiatives already have downloaded BOCG alternatives: `INI-3`/`tipoFich=3`/publication PDFs)
  - actionable tail: `0`
- Export packet for escalation/manual handling:
  - `docs/etl/sprints/AI-OPS-27/exports/senado_tail_missing_urls_20260222.csv` (`rows=119`)
  - `docs/etl/sprints/AI-OPS-27/exports/senado_tail_missing_urls_after_archive_20260222.csv` (`rows=119`)
  - `docs/etl/sprints/AI-OPS-27/exports/senado_tail_actionable_post_redundant_filter_20260222.csv` (`rows=0`)
- Consolidated KPI/status packet:
  - `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_20260222T103042Z.json`
  - `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_enhanced_postcleanup_20260222T140610Z.json`
  - `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_enhanced_detailfallback_20260222T140646Z.json`
  - `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_redundant_global_triage_20260222T142835Z.json`
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_redundant_global_skip_run_20260222T142846Z.json`
  - `docs/etl/sprints/AI-OPS-27/reports/initiative-doc-status-report-20260222.md`
  - `docs/etl/sprints/AI-OPS-27/reports/senado-tail-triage-20260222.md`
  - `docs/etl/sprints/AI-OPS-27/reports/senado-redundant-global-skip-20260222.md`
  - `docs/etl/sprints/AI-OPS-27/evidence/quality_initiatives_doclink_kpis_20260222T133754Z.json`
  - `docs/etl/sprints/AI-OPS-27/evidence/quality_initiatives_actionable_kpis_20260222T143924Z.json`
  - `docs/etl/sprints/AI-OPS-27/reports/initiative-quality-kpis-extension-20260222.md`
  - `docs/etl/sprints/AI-OPS-27/reports/senado-pdf-analysis-queue-empty-20260222.md`

## Command evidence used
```bash
sqlite3 etl/data/staging/politicos-es.db "WITH t AS (SELECT COUNT(*) total FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id WHERE i.source_id='senado_iniciativas'), d AS (SELECT COUNT(*) done FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs' WHERE i.source_id='senado_iniciativas' AND td.source_record_pk IS NOT NULL) SELECT t.total,d.done,(t.total-d.done),printf('%.2f',100.0*d.done/t.total) FROM t,d;"
```

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT pid.doc_kind, COUNT(*) total, SUM(CASE WHEN td.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) downloaded FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs' WHERE i.source_id='senado_iniciativas' GROUP BY pid.doc_kind ORDER BY pid.doc_kind;"
```

## Operational conclusion
- This is currently a stale-upstream-link tail (`global_enmiendas_vetos` `404`) on initiatives that already have downloaded BOCG alternatives.
- Keep periodic retries for reopen windows only when there is a new lever; default run path now skips this redundant Senate tail.
- Use the hardened daemon (`scripts/senado_tail_daemon.sh`) to avoid infinite loops when no new lever exists; see `docs/etl/sprints/AI-OPS-27/reports/senado-tail-daemon-anti-stall-20260222.md`.
- Controllable progress shipped in parallel: excerpt coverage for downloaded initiative docs is now `100%` (`9016/9016`) via `scripts/backfill_initiative_doc_excerpts.py` (see `docs/etl/sprints/AI-OPS-27/reports/initiative-doc-excerpt-backfill-20260222.md`).
- Post-triage queue check is empty for Senate missing-excerpt analysis (`rows=0`): `docs/etl/sprints/AI-OPS-27/reports/senado-pdf-analysis-queue-empty-20260222.md`.
