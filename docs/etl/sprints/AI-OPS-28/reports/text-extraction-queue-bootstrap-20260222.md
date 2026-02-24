# Text Extraction Queue Bootstrap (AI-OPS-28)

Date:
- 2026-02-22

Objective:
- Start AI-OPS-28 with a deterministic `text_documents` extraction queue that can be processed offline (no upstream re-fetch), deduped by checksum.

New tooling:
- `scripts/export_text_extraction_queue.py`
  - Filters by `source_id` and format (`pdf,html,xml,other`).
  - Supports `--only-missing-excerpt` to isolate pending extraction work.
  - Dedupe key strategy (`--dedupe-by`) defaults to `content_sha256` with fallback to `raw_path`/`source_record_pk`.
  - Emits queue CSV + JSON summary for reproducible handoffs.

Commands run:
```bash
python3 scripts/export_text_extraction_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-ids 'parl_initiative_docs,congreso_intervenciones,programas_partidos' \
  --formats 'pdf,html,xml' \
  --dedupe-by content_sha256 \
  --out docs/etl/sprints/AI-OPS-28/exports/text_extraction_queue_full_20260222T1600Z.csv \
  --summary-out docs/etl/sprints/AI-OPS-28/evidence/text_extraction_queue_full_summary_20260222T1600Z.json

python3 scripts/export_text_extraction_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-ids 'parl_initiative_docs,congreso_intervenciones,programas_partidos' \
  --formats 'pdf,html,xml' \
  --only-missing-excerpt \
  --dedupe-by content_sha256 \
  --out docs/etl/sprints/AI-OPS-28/exports/text_extraction_queue_missing_20260222T1600Z.csv \
  --summary-out docs/etl/sprints/AI-OPS-28/evidence/text_extraction_queue_missing_summary_20260222T1600Z.json
```

Results:
- Full queue summary:
  - `rows_scanned=9549`
  - `queue_items_total=8975`
  - `refs_total_written=9539`
  - `queue_items_pending=0`
  - `refs_missing_excerpt_all=0`
  - `refs_missing_raw_file_all=0`
- Missing-only queue summary:
  - `queue_items_total=0`
  - `queue_items_pending=0`
- Output files:
  - `docs/etl/sprints/AI-OPS-28/exports/text_extraction_queue_full_20260222T1600Z.csv`
  - `docs/etl/sprints/AI-OPS-28/exports/text_extraction_queue_missing_20260222T1600Z.csv`
  - `docs/etl/sprints/AI-OPS-28/evidence/text_extraction_queue_full_summary_20260222T1600Z.json`
  - `docs/etl/sprints/AI-OPS-28/evidence/text_extraction_queue_missing_summary_20260222T1600Z.json`

Interpretation:
- The excerpt backfill lane is currently drained (`missing=0`).
- The new full queue remains useful as deterministic batch input for deeper semantic extraction/classification work by subagents.

Operational shortcuts added:
- `just parl-export-text-extraction-queue`
- `just parl-export-text-extraction-queue-missing`
