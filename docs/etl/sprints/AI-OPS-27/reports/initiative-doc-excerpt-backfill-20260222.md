# Initiative Doc Excerpt Backfill (2026-02-22)

## Goal
Improve usable evidence coverage without relying on upstream network availability by extracting text excerpts from already-downloaded raw files in `text_documents`.

## Implementation
New script:
- `scripts/backfill_initiative_doc_excerpts.py`

Capabilities:
- Backfill `text_excerpt` + `text_chars` for missing rows.
- XML-aware extraction via `ElementTree.itertext()` (preserves CDATA content).
- PDF extraction via python libs with fallback to system `pdftotext`.
- Optional source scoping (`--initiative-source-id`), dry-run, and limit.

## Runs and evidence
- Senate pass 1 (XML baseline):
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_excerpt_backfill_20260222.json`
  - `updated=3034`
- Senate pass 2 (CDATA fix):
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_excerpt_backfill_20260222_r2.json`
  - `updated=1233`
- Global PDF pass (pdftotext fallback):
  - `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_excerpt_backfill_all_20260222.json`
  - `updated=729`

## KPI delta
Global (`source_id='parl_initiative_docs'`):
- Before: `missing_excerpt=4996` of `8883`
- After: `missing_excerpt=0` of `8883`

Senate subset (`senado_iniciativas` downloaded docs):
- Before: `missing_excerpt=4267` of `8154`
- After: `missing_excerpt=0` of `8154`
- Validation export (post-backfill queue is empty):
  - `docs/etl/sprints/AI-OPS-27/exports/senado_pdf_analysis_queue_missing_excerpt_20260222.csv` (`rows=0`)

## Repro commands
```bash
python3 scripts/backfill_initiative_doc_excerpts.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --initiative-source-id senado_iniciativas

python3 scripts/backfill_initiative_doc_excerpts.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs
```

## Why this matters
- Even with the final Senate tail blocked (`119` URLs with persistent `HTTP 500`), downstream analysis and citizen-facing explainability improve immediately because downloaded docs are now text-accessible.
