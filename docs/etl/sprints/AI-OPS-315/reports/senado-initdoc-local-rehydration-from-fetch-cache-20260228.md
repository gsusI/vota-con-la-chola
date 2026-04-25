# AI-OPS-315 — Rehidratación local de docs de iniciativas Senado desde `document_fetches`

## Objetivo

Reducir la cola accionable de `820/822` con trabajo 100% controlable por repo (sin red):
- reaprovechar `document_fetches.fetched_ok=1` con `raw_path` ya presente,
- re-linkear `parl_initiative_documents.source_record_pk`,
- mantener cobertura semántica (`parl_initiative_doc_extractions`) en `100%`.

## Ejecución

DB: `etl/data/staging/politicos-es.db`

1. Baseline:
- `report_initiative_doc_status` pre-run.
- Conteo `fetch_ok` sin `source_record_pk`.

2. Rehidratación local (sin red):
- `python3 scripts/backfill_initiative_doc_records_from_fetches.py --initiative-source-id senado_iniciativas ...`

3. Cierre de regresión de extracción (post-rehidratación):
- `python3 scripts/backfill_initiative_doc_extractions.py --initiative-source-ids senado_iniciativas --only-missing ...`

4. Re-medición:
- `report_initiative_doc_status` post-run,
- `report_senado_waf_block_profile --only-linked-to-votes`,
- export de cola accionable Senado (`only_linked_to_votes + only_actionable_missing`),
- gate de captura manual (`report_senado_manual_capture_validity --strict`).

## Resultado

- Rehidratación aplicada: `candidate_urls_total=86`, `usable_candidates_total=86`, `mapping_rows_updated=86`.
- Delta global (`initiative_doc_status`):
  - `downloaded_doc_links: 4248 -> 4334` (`+86`)
  - `missing_doc_links: 5305 -> 5219` (`-86`)
  - `missing_doc_links_actionable: 5088 -> 5035` (`-53`)
  - `effective_downloaded_doc_links_pct: 45.5 -> 46.26` (`+0.76pp`)
- Delta Senado (`initiative_doc_status`):
  - `downloaded_doc_links: 3436 -> 3522` (`+86`)
  - `missing_doc_links: 5305 -> 5219` (`-86`)
  - `missing_doc_links_actionable: 5088 -> 5035` (`-53`)
- Cierre de extracción post-rehidratación:
  - `seen=86`, `upserted=86`
  - `downloaded_missing_extraction=0` y `extraction_coverage_pct=100.0`.
- Cola Senado `only_linked_to_votes` vs AI-OPS-314:
  - CSV: `1313 -> 1260` líneas (incluye cabecera), delta `-53` filas accionables.
  - Perfil WAF: `missing_urls 1312 -> 1259`, `blocked_403_urls 717 -> 705`.

## Estado / bloqueo

- Progreso visible: **YES** (recuperación local medible en DB real, sin depender de upstream).
- Bloqueo externo persiste:
  - `senado_manual_capture_validity status=degraded`
  - `usable_captures_total=0`
  - strict `rc=4`.

## Evidencia

- `docs/etl/sprints/AI-OPS-315/evidence/backfill_from_fetches_apply_senado_20260228T221747Z.json`
- `docs/etl/sprints/AI-OPS-315/evidence/backfill_initiative_doc_extractions_apply_senado_20260228T221747Z.json`
- `docs/etl/sprints/AI-OPS-315/evidence/initiative_doc_status_before_20260228T221747Z.json`
- `docs/etl/sprints/AI-OPS-315/evidence/initiative_doc_status_after_extractions_20260228T221747Z.json`
- `docs/etl/sprints/AI-OPS-315/evidence/initiative_doc_status_delta_ai_ops_315_20260228T221747Z.json`
- `docs/etl/sprints/AI-OPS-315/evidence/senado_waf_block_profile_after_20260228T221747Z.json`
- `docs/etl/sprints/AI-OPS-315/evidence/senado_waf_block_profile_delta_vs_ai_ops_314_20260228T221747Z.json`
- `docs/etl/sprints/AI-OPS-315/exports/senado_tail_actionable_after_20260228T221747Z.csv`
- `docs/etl/sprints/AI-OPS-315/evidence/senado_tail_actionable_delta_vs_ai_ops_314_20260228T221747Z.json`
- `docs/etl/sprints/AI-OPS-315/evidence/senado_manual_capture_validity_20260228T221747Z.json`
- `docs/etl/sprints/AI-OPS-315/evidence/senado_manual_capture_validity_20260228T221747Z.rc`
- `docs/etl/sprints/AI-OPS-315/evidence/unittest_backfill_initiative_doc_records_from_fetches_20260228T221747Z.txt`
- `docs/etl/sprints/AI-OPS-315/evidence/unittest_backfill_initiative_docs_rehydration_and_extractions_20260228T221747Z.txt`
