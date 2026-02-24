# Initiative Quality Extraction Gate (AI-OPS-28)

Date:
- 2026-02-22

Objective:
- Make extraction quality visible in canonical `quality-report --include-initiatives` and enforce regression guardrails.

Shipped:
- `etl/parlamentario_es/quality.py`
  - initiative KPI model now includes extraction metrics:
    - `downloaded_doc_links_with_extraction`
    - `downloaded_doc_links_missing_extraction`
    - `extraction_needs_review_doc_links`
    - `extraction_coverage_pct`
    - `extraction_needs_review_pct`
    - `extraction_review_closed_pct`
  - initiative default gate thresholds now include:
    - `extraction_coverage_pct >= 0.95`
    - `extraction_review_closed_pct >= 0.95`
- tests:
  - `tests/test_parl_quality.py`
  - `tests/test_cli_quality_report.py`
- CLI enforce-gate coverage:
  - fail path when extraction backlog remains (`extraction_review_closed_pct` below threshold)
  - pass path when extraction backlog is closed
- `justfile`:
  - `parl-quality-pipeline` now executes `quality-report --include-initiatives --enforce-gate`
  - added shortcuts `parl-quality-report-initiatives` and `parl-quality-report-initiatives-enforce`.

Validation (real DB):
```bash
python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --source-ids congreso_votaciones,senado_votaciones \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --json-out docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_extraction_kpis_20260222T152859Z.json
```

Results:
- Initiative gate: `passed=true`
- Extraction KPIs (overall initiatives):
  - `downloaded_doc_links=9016`
  - `downloaded_doc_links_with_extraction=9016`
  - `downloaded_doc_links_missing_extraction=0`
  - `extraction_coverage_pct=1.0`
  - `extraction_needs_review_doc_links=0`
  - `extraction_needs_review_pct=0.0`
  - `extraction_review_closed_pct=1.0`
- Tail remains unchanged and non-actionable:
  - `missing_doc_links=119`
  - `missing_doc_links_actionable=0`
- Enforce-gate check:
  - `python3 scripts/ingestar_parlamentario_es.py quality-report ... --include-initiatives --enforce-gate` returns exit `0`.
  - updated artifact: `docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_extraction_gate_enforce_20260222T153541Z.json`

Evidence:
- `docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_extraction_kpis_20260222T152859Z.json`
- `docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_extraction_gate_enforce_20260222T153541Z.json`

Outcome:
- Extraction quality moved from ad-hoc sprint evidence into the canonical quality gate path.
- Future regressions in extraction coverage or review backlog now show up in standard `quality-report` outputs.
