# Senado Actionable Tail Gate (AI-OPS-61)

Date:
- 2026-02-22

Summary:
- Added actionable-only queue export and strict-empty gate in `scripts/export_missing_initiative_doc_urls.py`.
- Added just wrappers for routine export and strict queue-empty checks.
- Verified on `etl/data/staging/politicos-es.db` that Senado actionable queue is `0` and redundant global tail excluded is `119`.

Operational commands:
- `python3 scripts/export_missing_initiative_doc_urls.py --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --only-actionable-missing --format csv --out docs/etl/sprints/AI-OPS-61/exports/senado_tail_actionable_20260222T232623Z.csv`
- `python3 scripts/export_missing_initiative_doc_urls.py --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --only-actionable-missing --strict-empty --format csv --out docs/etl/sprints/AI-OPS-61/exports/senado_tail_actionable_strict_20260222T232623Z.csv`
- `INITDOC_MISSING_EXPORT_OUT=docs/etl/sprints/AI-OPS-61/exports/senado_tail_actionable_just_20260222T232623Z.csv just parl-export-missing-initdoc-urls-actionable`
- `INITDOC_MISSING_EXPORT_OUT=docs/etl/sprints/AI-OPS-61/exports/senado_tail_actionable_just_strict_20260222T232623Z.csv just parl-check-missing-initdoc-urls-actionable-empty`

Evidence:
- Export run: `docs/etl/sprints/AI-OPS-61/evidence/senado_tail_actionable_export_20260222T232623Z.txt`
- Strict run: `docs/etl/sprints/AI-OPS-61/evidence/senado_tail_actionable_strict_20260222T232623Z.txt`
- Report snapshot: `docs/etl/sprints/AI-OPS-61/evidence/initiative_doc_status_20260222T232623Z.json`
- Run codes: `docs/etl/sprints/AI-OPS-61/evidence/ai_ops_61_run_codes_20260222T232623Z.txt`
- Unit tests: `docs/etl/sprints/AI-OPS-61/evidence/python_tests_ai_ops_61_20260222T232623Z.txt`
