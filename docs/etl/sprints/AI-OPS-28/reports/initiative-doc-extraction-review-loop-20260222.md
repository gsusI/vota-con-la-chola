# Initiative Doc Extraction Review Loop (AI-OPS-28)

Date:
- 2026-02-22

Objective:
- Close the operational loop for initiative-doc extraction adjudication: export batch -> annotate decisions -> apply back to SQLite deterministically.

Shipped:
- Apply script:
  - `scripts/apply_initdoc_extraction_reviews.py`
  - Input CSV contract (round-trip from queue export):
    - `source_record_pk`
    - `review_status` (`resolved|ignored|pending`)
    - optional overrides: `final_subject`, `final_title`, `final_confidence`
    - audit fields: `review_note`, `reviewer`
  - Writes decisions into `parl_initiative_doc_extractions`:
    - updates `needs_review`
    - applies optional subject/title/confidence overrides
    - appends review metadata/history in `analysis_payload_json`
- Queue exporter updated:
  - `scripts/export_initdoc_extraction_review_queue.py`
  - now emits decision columns to support direct round-trip.
- Ops shortcuts (`justfile`):
  - `just parl-export-initdoc-extraction-review-queue`
  - `just parl-apply-initdoc-extraction-reviews`
  - `just parl-apply-initdoc-extraction-reviews-dry-run`

Validation:
- Tests added/passing:
  - `tests/test_apply_initdoc_extraction_reviews.py`
  - `tests/test_export_initdoc_extraction_review_queue.py`
- Combined regression run passed:
  - `python3 -m unittest tests.test_apply_initdoc_extraction_reviews tests.test_backfill_initiative_doc_extractions tests.test_export_initdoc_extraction_review_queue tests.test_export_text_extraction_queue tests.test_report_initiative_doc_status tests.test_parl_quality tests.test_cli_quality_report tests.test_parl_text_documents -q`

Commands run:
```bash
python3 scripts/export_initdoc_extraction_review_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --only-needs-review \
  --limit 200 \
  --out docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0001_20260222T1640Z.csv

python3 scripts/apply_initdoc_extraction_reviews.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --in docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0001_20260222T1640Z.csv \
  --dry-run \
  --out docs/etl/sprints/AI-OPS-28/evidence/initdoc_extraction_review_apply_dryrun_20260222T1640Z.json
```

Results:
- Batch artifact created:
  - `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0001_20260222T1640Z.csv`
  - rows: `200`
- Dry-run apply output:
  - `rows_seen=200`
  - `rows_with_decision=0`
  - `updated=0`
  - `skipped_blank_status=200`
  - artifact: `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extraction_review_apply_dryrun_20260222T1640Z.json`

Interpretation:
- The loop is now ready for mechanical adjudication without custom scripts per batch.
- Next immediate action is to populate `review_status` + optional override columns in batch CSVs and run non-dry apply.
