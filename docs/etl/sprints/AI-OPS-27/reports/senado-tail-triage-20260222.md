# Senado Tail Triage (2026-02-22)

## Scope
- Source: `senado_iniciativas`
- Objective: stop blind retries and isolate the truly actionable tail.
- DB: `etl/data/staging/politicos-es.db`

## What shipped
- Downloader enhancement in `etl/parlamentario_es/text_documents.py`:
  - For Senado `global_enmiendas_vetos_*`, derive candidate `INI-3-*.xml` URL and prioritize it when `max-docs-per-initiative` is low.
  - New counters in backfill output: `derived_ini_candidates`, `derived_ini_selected`, `derived_probe_unfetched_skipped`.
  - Guardrail: unfetched derived probes are **not** persisted into `parl_initiative_documents` (prevents artificial growth of `total_doc_links`).
- Status report enhancement in `scripts/report_initiative_doc_status.py`:
  - Adds `missing_doc_links_likely_not_expected`, `missing_doc_links_actionable`, `effective_downloaded_doc_links_pct`.
  - Adds `global_enmiendas_vetos_analysis` for `senado_iniciativas`.
  - Adds Senate classification `likely_not_expected_redundant_global_url` when the initiative already has downloaded BOCG alternatives (`INI-3`, `tipoFich=3`, or Senado publication PDFs).
- Queue guard in `etl/parlamentario_es/text_documents.py`:
  - Skips stale Senate `global_enmiendas_vetos` URLs (and their derived `INI-3` probes) when a BOCG alternative is already downloaded.
  - New counter in backfill output: `skipped_redundant_global_urls`.

## Evidence runs

Derived INI probe (before non-persistence guard was added):
- `docs/etl/sprints/AI-OPS-27/evidence/initdoc_derived_ini_probe_20260222T140436Z.json`
- Result: `derived_ini_candidates=8`, `urls_to_fetch=8`, all 8 returned `HTTP 404`.

Post-fix derived probe (no metric inflation):
- `docs/etl/sprints/AI-OPS-27/evidence/initdoc_derived_ini_probe_postfix_20260222T140611Z.json`
- Result: `derived_ini_candidates=8`, `derived_ini_selected=8`, `derived_probe_unfetched_skipped=8`, `urls_to_fetch=0`.

Enhanced status snapshot:
- `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_enhanced_postcleanup_20260222T140610Z.json`

## Current tail decomposition
From enhanced status snapshot (redundant-global triage enabled):
- `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_redundant_global_triage_20260222T142835Z.json`
- Senado raw missing: `119`
- `global_enmiendas_vetos_analysis.total_global_enmiendas_missing`: `119`
- `likely_not_expected_redundant_global_url`: `119`
- `likely_not_expected_total`: `119`
- `actionable_missing_count`: `0`
- `no_ini_downloaded`: `0`

Interpretation:
- All `119` missing Senate links are stale `global_enmiendas_vetos` URLs that are now classified as non-actionable because the same initiatives already have downloadable BOCG alternatives materialized.
- Actionable packet after redundant filter:
  - `docs/etl/sprints/AI-OPS-27/exports/senado_tail_actionable_post_redundant_filter_20260222.csv` (`rows=0`)
- Backfill run evidence with redundant-skip guard:
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_redundant_global_skip_run_20260222T142846Z.json` (`urls_to_fetch=0`, `skipped_redundant_global_urls=127`)

## Coverage metrics (same snapshot)
- Overall: `9016/9135` (`98.70%`)
- Overall effective (excluding likely-not-expected tail): `100.00%`
- Senado raw: `8204/8323` (`98.57%`)
- Senado effective (excluding likely-not-expected tail): `100.00%`

## Operational conclusion
- No further blind bulk retries on Senate `global_enmiendas_vetos` URLs while no new lever exists.
- Keep blocker evidence append-only and treat current residual missing set as non-actionable technical debt unless upstream republishes those stale endpoints.
