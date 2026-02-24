# Initiative Doc Extraction Review Batch Pack (AI-OPS-28)

Date:
- 2026-02-22

Objective:
- Produce deterministic, ready-to-review batch files for the remaining extraction queue.

Shipped:
- `scripts/export_initdoc_extraction_review_queue.py`
  - new args: `--offset` (paging)
  - exported CSV now includes `subject_method`.
- tests updated:
  - `tests/test_export_initdoc_extraction_review_queue.py`

Commands run:
```bash
python3 scripts/export_initdoc_extraction_review_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --only-needs-review \
  --limit 200 --offset 0 \
  --out docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0001_of_0003_20260222T151410Z.csv

python3 scripts/export_initdoc_extraction_review_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --only-needs-review \
  --limit 200 --offset 200 \
  --out docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0002_of_0003_20260222T151410Z.csv

python3 scripts/export_initdoc_extraction_review_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --only-needs-review \
  --limit 200 --offset 400 \
  --out docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0003_of_0003_20260222T151410Z.csv
```

Results:
- Batch packet generated:
  - batch 1: `200` rows
  - batch 2: `200` rows
  - batch 3: `190` rows
  - total: `590` rows
- Method split (`subject_method`) across packet:
  - `keyword_window=372`
  - `title_hint=218`

Evidence:
- `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extraction_review_batches_queued_latest.json`
- `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0001_of_0003_20260222T151410Z.csv`
- `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0002_of_0003_20260222T151410Z.csv`
- `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0003_of_0003_20260222T151410Z.csv`
