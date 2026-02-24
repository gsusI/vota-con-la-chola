# Senado Redundant Global Skip (2026-02-22)

## Scope
- Source: `senado_iniciativas`
- DB: `etl/data/staging/politicos-es.db`
- Goal: stop wasting queue cycles on stale `global_enmiendas_vetos` URLs that are redundant once alternative BOCG docs are already downloaded.

## What changed
- Downloader (`etl/parlamentario_es/text_documents.py`):
  - skips Senate `global_enmiendas_vetos` URLs (and derived `INI-3` probes) when a downloaded BOCG alternative exists for that initiative (`INI-3`, `tipoFich=3`, or Senado publication PDF).
  - emits new counter: `skipped_redundant_global_urls`.
- Status report (`scripts/report_initiative_doc_status.py`):
  - adds Senate classification `likely_not_expected_redundant_global_url` and `likely_not_expected_total`.
- Missing URL export (`scripts/export_missing_initiative_doc_urls.py`):
  - adds `--exclude-redundant-senado-global` to export only actionable rows.

## Evidence
- Queue pass (real run, not dry-run):
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_redundant_global_skip_run_20260222T142846Z.json`
  - Result: `initiatives_seen=119`, `urls_to_fetch=0`, `skipped_redundant_global_urls=127`, `fetched_ok=0`.
- Status snapshot:
  - `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_redundant_global_triage_20260222T142835Z.json`
  - Result: Senate `missing=119`, `likely_not_expected_redundant_global_url=119`, `actionable_missing_count=0`, effective downloaded pct `100.00%`.
- Actionable export after redundant filter:
  - `docs/etl/sprints/AI-OPS-27/exports/senado_tail_actionable_post_redundant_filter_20260222.csv`
  - Result: `rows=0`.

## Validation
- `python3 -m unittest tests.test_parl_quality tests.test_cli_quality_report tests.test_parl_text_documents tests.test_report_initiative_doc_status -q`
- Result: `Ran 15 tests ... OK`.

## Operational outcome
- Default Senate queue processing now avoids retry churn on known stale global URLs.
- Tail remains visible in raw metrics (`119` missing), but is correctly triaged as non-actionable under current available evidence.
