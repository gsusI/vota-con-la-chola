# Initiative Doc Extractions `title_hint_strong` (AI-OPS-28)

Date:
- 2026-02-22

Objective:
- Reduce `needs_review` debt in `parl_initiative_doc_extractions` using deterministic, conservative logic (no new network calls).

What changed:
- `scripts/backfill_initiative_doc_extractions.py`
  - new extractor path `title_hint_strong` for long, explicit legislative titles.
  - default extractor version bumped to `heuristic_subject_v2`.
- `justfile`
  - `parl-backfill-initdoc-extractions*` now call `--extractor-version heuristic_subject_v2`.
- Tests:
  - added `test_title_hint_strong_auto_clears_review` in `tests/test_backfill_initiative_doc_extractions.py`.

Commands run:
```bash
python3 scripts/report_initiative_doc_status.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_before_title_hint_strong_20260222T151026Z.json

python3 scripts/backfill_initiative_doc_extractions.py \
  --db etl/data/staging/politicos-es.db \
  --extractor-version heuristic_subject_v2 \
  --out docs/etl/sprints/AI-OPS-28/evidence/initdoc_extractions_backfill_title_hint_strong_20260222T151026Z.json

python3 scripts/report_initiative_doc_status.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_after_title_hint_strong_20260222T151026Z.json

python3 scripts/export_initdoc_extraction_review_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --only-needs-review \
  --out docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_queue_after_title_hint_strong_20260222T151026Z.csv
```

Results:
- Backfill:
  - `upserted=8932`
  - method split: `keyword_window=5197`, `keyword_sentence=13`, `title_hint_strong=3504`, `title_hint=218`
- Review debt drop (`report_initiative_doc_status`):
  - before: `extraction_needs_review=4096` (`45.43%` of downloaded doc-links)
  - after: `extraction_needs_review=592` (`6.57%`)
  - delta: `-3504` doc-links flagged for manual review
- Queue export after v2:
  - `590` rows (`source_record_pk` docs)
  - `by_method`: `keyword_window=372`, `title_hint=218`
  - `by_doc_format`: `xml=353`, `html=204`, `pdf=31`, `other=2`

Artifacts:
- `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extractions_backfill_title_hint_strong_20260222T151026Z.json`
- `docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_before_title_hint_strong_20260222T151026Z.json`
- `docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_after_title_hint_strong_20260222T151026Z.json`
- `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extraction_review_queue_after_title_hint_strong_20260222T151026Z.json`
- `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_queue_after_title_hint_strong_20260222T151026Z.csv`

Interpretation:
- This is a controllable sprint delta that cuts manual queue volume without upstream dependencies.
- Remaining queue is now concentrated in truly ambiguous extractions (`keyword_window` short/edge cases + weaker `title_hint`).
