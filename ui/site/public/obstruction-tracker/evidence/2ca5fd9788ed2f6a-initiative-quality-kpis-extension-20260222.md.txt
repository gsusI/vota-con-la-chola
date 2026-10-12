# Initiative Quality KPI Extension (2026-02-22)

## Objective
Move initiative-doc operational metrics into the canonical `quality-report` path so teams do not need custom SQL or ad-hoc scripts to evaluate progress.

## Code change
- Extended `etl/parlamentario_es/quality.py`:
  - `compute_initiative_quality_kpis()` now emits doc-link-level metrics, by source and overall:
    - `total_doc_links`, `downloaded_doc_links`, `missing_doc_links`, `downloaded_doc_links_pct`
    - `missing_doc_links_likely_not_expected`, `missing_doc_links_actionable`, `effective_downloaded_doc_links_pct`
    - `doc_links_with_fetch_status`, `doc_links_missing_fetch_status`, `fetch_status_coverage_pct`
    - `downloaded_doc_links_with_excerpt`, `downloaded_doc_links_missing_excerpt`, `excerpt_coverage_pct`
    - `missing_doc_links_status_buckets` (status histogram for missing docs)
    - Senate-only split in `by_source.senado_iniciativas.global_enmiendas_vetos_analysis`:
      - `total_global_enmiendas_missing`
      - `likely_not_expected_redundant_global_url`
      - `likely_not_expected_total`
      - `actionable_missing_count`
- Backward-compatible: existing KPI keys remain unchanged.

## Evidence run
Command:
```bash
python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --json-out docs/etl/sprints/AI-OPS-27/evidence/quality_initiatives_doclink_kpis_20260222T133754Z.json
```

Evidence:
- `docs/etl/sprints/AI-OPS-27/evidence/quality_initiatives_doclink_kpis_20260222T133754Z.json`
- `docs/etl/sprints/AI-OPS-27/evidence/quality_initiatives_actionable_kpis_20260222T143924Z.json`

Observed values:
- Overall doc-link download: `9016/9135` (`0.9870`)
- Overall missing split: `119 likely_not_expected`, `0 actionable`
- Overall effective download pct (excluding likely-not-expected): `1.0`
- Senado missing split: `119 likely_not_expected_redundant_global_url`, `0 actionable`
- Fetch-status coverage: `9135/9135` (`1.0`)
- Excerpt coverage on downloaded docs: `9016/9016` (`1.0`)
- Missing status bucket: `404=119`

## Operational impact
- Initiative quality snapshots now include first-class tail diagnostics in the same artifact used for gates and publishing workflows.
- `scripts/report_initiative_doc_status.py` remains useful for richer operational details (missing URL samples + doc-kind breakdown), but core KPI truth now lives in one canonical command.

## Regression coverage
- Added tests:
  - `tests/test_parl_quality.py::TestParlInitiativeQuality::test_compute_initiative_kpis_include_doc_link_fetch_excerpt_metrics`
  - `tests/test_parl_quality.py::TestParlInitiativeQuality::test_compute_initiative_kpis_classifies_redundant_senado_global_links`
  - `tests/test_cli_quality_report.py::TestParlCliQualityReport::test_quality_report_include_initiatives_exposes_doc_link_kpis`
- Verification command:
```bash
python3 -m unittest tests.test_parl_quality tests.test_cli_quality_report
```
- Result on this sprint checkpoint:
  - `Ran 10 tests ... OK`
