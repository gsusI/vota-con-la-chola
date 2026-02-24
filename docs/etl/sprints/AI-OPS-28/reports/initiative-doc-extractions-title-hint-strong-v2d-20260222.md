# Initiative Doc Extractions `title_hint_strong` Refinement v2d (AI-OPS-28)

Date:
- 2026-02-22

Objective:
- Further reduce deterministic review debt by improving strong-title detection for formal initiative titles (no network calls).

What changed:
- `scripts/backfill_initiative_doc_extractions.py`
  - expanded `_STRONG_TITLE_PATTERNS` for formal legal/international instrument titles (`protocolo`, `convención`, `actas`, `memorándum`, `declaraciones`, `resoluciones`, `canje`, `código`, etc.).
  - lowered strong-title minimum length from `50` to `35`.
  - added explicit terms `documento` and `modificación`.
  - method-specific review threshold: `title_hint_strong` / `title_fallback_strong` now use min length `38` (vs default `40`).
- tests:
  - `tests/test_backfill_initiative_doc_extractions.py` now covers:
    - explicit international-act titles
    - short but explicit strong titles (`Proyecto de Ley ... (621/...)`).

Evidence sequence (real DB `etl/data/staging/politicos-es.db`):
- Initial baseline after first strong-title pass:
  - before: `extraction_needs_review=592` (`6.57%`)
- Refinement pass B:
  - after: `extraction_needs_review=384` (`4.26%`)
  - artifacts:
    - `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extractions_backfill_title_hint_strong_v2b_20260222T151814Z.json`
    - `docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_before_title_hint_strong_v2b_20260222T151814Z.json`
    - `docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_after_title_hint_strong_v2b_20260222T151814Z.json`
- Refinement pass C/D:
  - final: `extraction_needs_review=374` (`4.15%`)
  - remaining queue is now exclusively `keyword_window` (no `title_hint` debt).
  - artifacts:
    - `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extractions_backfill_title_hint_strong_v2c_20260222T151902Z.json`
    - `docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_after_title_hint_strong_v2c_20260222T151902Z.json`
    - `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extractions_backfill_title_hint_strong_v2d_20260222T152006Z.json`
    - `docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_after_title_hint_strong_v2d_20260222T152006Z.json`

Queue outputs:
- full review queue after v2d:
  - `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_queue_after_title_hint_strong_v2d_20260222T152006Z.csv`
  - `372` rows, split: `keyword_window=372`.
  - summary: `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extraction_review_queue_after_title_hint_strong_v2d_20260222T152006Z.json`
- deterministic batch pack for remaining queue:
  - `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0001_of_0002_20260222T152034Z.csv` (`200`)
  - `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0002_of_0002_20260222T152034Z.csv` (`172`)
  - summary: `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extraction_review_batches_queued_after_title_hint_strong_v2d_latest.json`

Outcome:
- From extraction bootstrap baseline (`4096` doc-links in review), controllable heuristic refinements reduced review debt to `374` (`-3722`, `-90.87%`), while keeping extraction coverage at `9016/9016` downloaded doc-links.
