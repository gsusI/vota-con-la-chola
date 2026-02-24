# Initiative Doc Extractions Bootstrap (AI-OPS-28)

Date:
- 2026-02-22

Objective:
- Persist a deterministic, idempotent semantic extraction layer for already-downloaded initiative docs ("qué se votó") directly in SQLite.

Shipped:
- Additive schema table:
  - `parl_initiative_doc_extractions`
  - key: `source_record_pk` (1 row per downloaded doc)
  - stores `extracted_subject`, `extracted_title`, `extracted_excerpt`, `confidence`, `needs_review`, `extractor_version`.
- Backfill script:
  - `scripts/backfill_initiative_doc_extractions.py`
- Review queue exporter:
  - `scripts/export_initdoc_extraction_review_queue.py`
- `just` shortcuts:
  - `just parl-backfill-initdoc-extractions`
  - `just parl-backfill-initdoc-extractions-missing`
  - `just parl-export-initdoc-extraction-review-queue`

Commands run:
```bash
python3 scripts/backfill_initiative_doc_extractions.py \
  --db etl/data/staging/politicos-es.db \
  --doc-source-id parl_initiative_docs \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --extractor-version heuristic_subject_v1 \
  --out docs/etl/sprints/AI-OPS-28/evidence/initdoc_extractions_backfill_20260222T1625Z.json

python3 scripts/backfill_initiative_doc_extractions.py \
  --db etl/data/staging/politicos-es.db \
  --doc-source-id parl_initiative_docs \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --extractor-version heuristic_subject_v1 \
  --only-missing \
  --out docs/etl/sprints/AI-OPS-28/evidence/initdoc_extractions_backfill_missing_post_20260222T1628Z.json

python3 scripts/export_initdoc_extraction_review_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --only-needs-review \
  --out docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_queue.csv

python3 scripts/report_initiative_doc_status.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --out docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_20260222T1635Z.json
```

Results:
- Backfill coverage:
  - `seen=8932`
  - `upserted=8932`
  - `extracted_subject non-empty = 8932` (SQL check)
  - `needs_review=4094`
- Method split:
  - `keyword_window=5197`
  - `keyword_sentence=13`
  - `title_hint=3722`
- Format split (`total / needs_review`):
  - `xml: 4257 / 450`
  - `html: 3887 / 3607`
  - `pdf: 778 / 35`
  - `other: 10 / 2`
- Source split (by sample initiative source):
  - `senado_iniciativas: 8203 (needs_review=4063)`
  - `congreso_iniciativas: 729 (needs_review=31)`
- Missing-only idempotence check after first pass:
  - `seen=0`, `upserted=0`
- Review queue export:
  - `rows=4094`
  - file: `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_queue.csv`
- Canonical status report extension:
  - extraction coverage fields now present in `report_initiative_doc_status` output:
    - `downloaded_with_extraction=9016`
    - `downloaded_missing_extraction=0`
    - `extraction_coverage_pct=100.0`
    - `extraction_needs_review=4096` (`45.43%`)
  - artifact: `docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_20260222T1635Z.json`
  - Nota de métrica: `4094` (backfill) cuenta documentos únicos (`source_record_pk`), mientras `4096` (status report) cuenta doc-links descargados; hay doc-links duplicados que comparten el mismo `source_record_pk`.

Interpretation:
- The extraction layer is now materialized and queryable in the DB; downstream workflows no longer depend on ad-hoc CSV-only derivations.
- Main review debt sits in HTML-heavy rows (`3607/3887`), which is expected due noisy boilerplate pages and conservative `needs_review` thresholds.
- The new queue enables bounded subagent/manual adjudication batches without touching upstream endpoints.
