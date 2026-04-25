# AI-OPS-226 - Fix de extracción para docs Congreso con excerpt vacío

Fecha (UTC): 2026-02-27

## Objetivo
Cerrar el gap controlable de extracción semántica en `congreso_iniciativas` cuando `text_documents.text_excerpt` está vacío pero existe `title` usable.

## Cambios implementados
- `scripts/backfill_initiative_doc_extractions.py`
  - La query de selección ya no excluye filas por `text_excerpt` vacío.
  - Nuevo criterio: incluir filas con `text_excerpt` no vacío **o** `sample_title` no vacío, habilitando fallback por título.
- `tests/test_backfill_initiative_doc_extractions.py`
  - Nueva regresión: `test_empty_excerpt_uses_title_fallback_strong`.
  - Verifica que se genera extracción con `subject_method=title_fallback_strong`, `confidence=0.74` y `needs_review=0` para `text_excerpt=NULL`.

## Validación de tests
- Comando:
  - `python3 -m unittest tests.test_backfill_initiative_doc_extractions tests.test_backfill_initiative_doc_records_from_fetches tests.test_parl_text_documents`
- Resultado:
  - `Ran 14 tests in 0.861s`
  - `OK`

## Corrida real en staging
- Comando:
  - `python3 scripts/backfill_initiative_doc_extractions.py --db etl/data/staging/politicos-es.db --doc-source-id parl_initiative_docs --initiative-source-ids congreso_iniciativas --extractor-version heuristic_subject_v2 --only-missing`
- Resultado:
  - `seen=729`, `upserted=729`, `needs_review=2`
  - `by_method`: `title_fallback_strong=727`, `title_fallback=2`

## Delta de calidad (postfix -> after fix)
- `downloaded_doc_links_with_extraction`: `3393 -> 4205` (`+812`)
- `downloaded_doc_links_missing_extraction`: `812 -> 0`
- `extraction_coverage_pct` (overall): `0.8069 -> 1.0`
- `extraction_review_closed_pct` (overall): `1.0 -> 0.9995` (por `2` links en revisión)
- `actionable_doc_links_closed_pct`: sin cambio (`0.4905`)

## Estado de gate
- `quality-report --include-initiatives --enforce-gate` sigue en `rc=1`.
- Fallo residual único: `actionable_doc_links_closed_pct` en cola Senado (`missing_doc_links_actionable=4441`).

## Cierre de cola de revisión residual (2 filas)
- Export de cola residual:
  - `python3 scripts/export_initdoc_extraction_review_queue.py --db etl/data/staging/politicos-es.db --source-id parl_initiative_docs --only-needs-review --limit 50 --out ...`
  - Resultado inicial: `rows=2`.
- Apply reproducible:
  - `python3 scripts/apply_initdoc_extraction_reviews.py --db etl/data/staging/politicos-es.db --in ... --source-id parl_initiative_docs --dry-run`
  - `python3 scripts/apply_initdoc_extraction_reviews.py --db etl/data/staging/politicos-es.db --in ... --source-id parl_initiative_docs`
  - Resultado: `updated=2`.
- Estado post-apply:
  - cola `needs_review` en `0` filas (`rows=0`).
  - `extraction_needs_review_doc_links=0`.
  - `extraction_review_closed_pct=1.0` (overall y Congreso).

## Evidencia
- `docs/etl/sprints/AI-OPS-226/evidence/initdoc_extractions_congreso_empty_excerpt_fix_latest.json`
- `docs/etl/sprints/AI-OPS-226/evidence/quality_initiatives_after_congreso_extraction_fix_latest.json`
- `docs/etl/sprints/AI-OPS-226/evidence/quality_initiatives_after_congreso_extraction_fix_enforce_latest.json`
- `docs/etl/sprints/AI-OPS-226/evidence/quality_initiatives_after_congreso_extraction_fix_enforce_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-226/evidence/quality_initiatives_delta_postfix_vs_congreso_extraction_fix_latest.csv`
- `docs/etl/sprints/AI-OPS-226/evidence/initdoc_extraction_review_residual_apply_latest.json`
- `docs/etl/sprints/AI-OPS-226/evidence/quality_initiatives_after_congreso_review_closure_latest.json`
- `docs/etl/sprints/AI-OPS-226/evidence/quality_initiatives_after_congreso_review_closure_enforce_latest.json`
- `docs/etl/sprints/AI-OPS-226/evidence/quality_initiatives_delta_after_fix_vs_review_closure_latest.csv`
- `docs/etl/sprints/AI-OPS-226/exports/initdoc_extraction_review_queue_residual_post_apply_latest.csv`
