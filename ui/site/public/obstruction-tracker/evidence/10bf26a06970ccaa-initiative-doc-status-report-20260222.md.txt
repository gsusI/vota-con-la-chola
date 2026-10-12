# Initiative Doc Status Report (2026-02-22)

## Command
```bash
python3 scripts/report_initiative_doc_status.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --missing-sample-limit 20 \
  --out docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_20260222T103042Z.json
```

## Snapshot
- DB: `etl/data/staging/politicos-es.db`
- Generated at: `2026-02-22T10:30:42Z`
- Evidence JSON: `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_20260222T103042Z.json`

## Overall
- `initiatives_total`: `4036`
- `initiatives_with_doc_links`: `4006` (`99.26%`)
- `total_doc_links`: `9135`
- `downloaded_doc_links`: `9016` (`98.70%`)
- `doc_links_with_fetch_status`: `9135` (`100%` coverage)
- `downloaded_with_excerpt`: `9016` (`100%` excerpt coverage on downloaded docs)
- `linked_to_votes_with_downloaded_docs`: `751/751` (`100%`)

## By source
- `congreso_iniciativas`
  - doc links: `812/812` downloaded (`100%`)
  - fetch-status coverage: `812/812` (`100%`)
  - excerpt coverage: `812/812` (`100%`)
  - linked-to-votes with downloaded docs: `104/104` (`100%`)
- `senado_iniciativas`
  - doc links: `8204/8323` downloaded (`98.57%`)
  - missing links: `119`
  - fetch-status coverage: `8323/8323` (`100%`)
  - excerpt coverage: `8204/8204` downloaded (`100%`)
  - linked-to-votes with downloaded docs: `647/647` (`100%`)
  - missing status bucket: `HTTP 404 = 119`

## Operational read
- Controllable KPI slices are now complete for:
  - fetch-status traceability on all initiative doc links (`100%`)
  - excerpt coverage on all downloaded initiative docs (`100%`)
  - linked-to-votes initiative doc download objective (`100%`)
- Open blocker remains bounded to Senate tail (`119` URLs, `HTTP 404` cluster).

## Addendum (tail triage update)
- Enhanced snapshot:
  - `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_enhanced_detailfallback_20260222T140646Z.json`
- Senate tail decomposition:
  - raw missing: `119`
  - likely-not-expected (`enmCantidad=0` via `INI-3` + `tipoFich=3` fallback): `115`
  - actionable unknown tail: `4`
- Effective KPI (excluding likely-not-expected tail):
  - Senado effective downloaded pct: `99.95%`
  - Overall effective downloaded pct: `99.96%`
- Drill-down report:
  - `docs/etl/sprints/AI-OPS-27/reports/senado-tail-triage-20260222.md`

## Addendum (redundant-global classification)
- Latest snapshot:
  - `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_redundant_global_triage_20260222T142835Z.json`
- Senate tail decomposition (latest):
  - raw missing: `119`
  - `likely_not_expected_redundant_global_url`: `119`
  - actionable tail: `0`
- Effective KPI (latest):
  - Senado effective downloaded pct: `100.00%`
  - Overall effective downloaded pct: `100.00%`
- Queue behavior checkpoint:
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_redundant_global_skip_run_20260222T142846Z.json` (`urls_to_fetch=0`, `skipped_redundant_global_urls=127`)
- Canonical quality artifact parity:
  - `docs/etl/sprints/AI-OPS-27/evidence/quality_initiatives_actionable_kpis_20260222T143924Z.json` (same actionable split in `initiatives.kpis`)
