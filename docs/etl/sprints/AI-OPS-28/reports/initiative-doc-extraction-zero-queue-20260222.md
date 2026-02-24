# Initiative Doc Extraction Zero Queue (AI-OPS-28)

Date:
- 2026-02-22

Objective:
- Finish the extraction review backlog for downloaded initiative docs with explicit, auditable decisions.

Baseline before this slice:
- After heuristic refinements: `extraction_needs_review=1` doc-link (`0.01%`).
- Residual item:
  - `source_record_pk=142249`
  - subject: `PROYECTOS DE LEY 8 de marzo de 2024 Núm`
  - initiative title: `Proyecto de Ley de Familias.`

Action taken:
- Created single-row review decision CSV:
  - `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_autoresolve_singleton_20260222T152337Z.csv`
- Applied decision through canonical review pipeline:
```bash
python3 scripts/apply_initdoc_extraction_reviews.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --in docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_autoresolve_singleton_20260222T152337Z.csv \
  --out docs/etl/sprints/AI-OPS-28/evidence/initdoc_extraction_review_apply_autoresolve_singleton_20260222T152337Z.json
```

Post-apply checks:
```bash
python3 scripts/report_initiative_doc_status.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_post_singleton_apply_20260222T152337Z.json

python3 scripts/export_initdoc_extraction_review_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --only-needs-review \
  --out docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_queue_post_singleton_apply_20260222T152337Z.csv
```

Results:
- Apply summary:
  - `rows_with_decision=1`
  - `updated=1`
- Status summary:
  - `downloaded_with_extraction=9016`
  - `downloaded_missing_extraction=0`
  - `extraction_needs_review=0`
  - `extraction_needs_review_pct=0.0`
- Queue summary:
  - review CSV rows: `0`
  - evidence json: `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extraction_review_queue_post_singleton_apply_20260222T152337Z.json`

Outcome:
- The extraction review backlog for downloaded initiative docs is now closed (`pending -> resolved/ignored` complete for current snapshot).
