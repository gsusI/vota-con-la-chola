# Senado PDF Analysis Queue Check (2026-02-22)

## Command
```bash
python3 scripts/export_pdf_analysis_queue.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --only-missing-excerpt \
  --out docs/etl/sprints/AI-OPS-27/exports/senado_pdf_analysis_queue_post_actionable_kpis_20260222.csv
```

## Result
- Output CSV: `docs/etl/sprints/AI-OPS-27/exports/senado_pdf_analysis_queue_post_actionable_kpis_20260222.csv`
- Rows: `0`

## Operational meaning
- There is no pending Senate downloaded-doc queue for excerpt extraction at this checkpoint.
- Subagent/manual PDF text analysis capacity can be reassigned to other ETL lanes until new docs arrive.
