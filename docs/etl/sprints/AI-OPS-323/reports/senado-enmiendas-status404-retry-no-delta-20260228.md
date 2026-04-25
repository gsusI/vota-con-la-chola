# AI-OPS-323 - Retry dirigido `enmiendas/index` (`status=404`) sin delta material

## Objetivo
Ejecutar un retry archivistico acotado sobre la cohorte `enmiendas/index.html` con `status=404` en cola Senado `only_linked_to_votes` para verificar recuperación incremental tras AI-OPS-322.

## Ejecución
1. Baseline
- `report_initiative_doc_status.py` (before)
- `report_senado_waf_block_profile.py --only-linked-to-votes` (before)
- `report_senado_manual_capture_validity.py --strict` (`status=degraded`, `strict_fail_reasons=[no_usable_capture]`, `rc=4`)

2. Packet dirigido
- `senado_enmiendas_index_status404_packet`: `80` URLs / `80` iniciativas.

3. Retry acotado (sin cookie usable)
- `backfill-initiative-documents --doc-urls-file <packet> --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404`
- Resultado:
  - `candidate_urls=80`, `urls_to_fetch=80`
  - `fetched_ok=0`, `archive_hits=0`, `archive_fetched_ok=0`, `text_documents_upserted=0`
  - `initiative_documents_upserted=80` (trazabilidad), `selected_scope_no_limit=true`
  - `failures=30` (`archive fallback: no snapshot candidates`).

4. Post-proceso de estructuracion
- `backfill_initiative_doc_extractions.py --only-missing --initiative-source-ids senado_iniciativas`
- Resultado: `seen=0`, `upserted=0`, `needs_review=0`.

## Delta medido
- Cobertura global iniciativas: sin cambios (`downloaded_doc_links=4379`, `missing_doc_links_actionable=4990`).
- Senado (`by_source`): sin cambios (`downloaded_doc_links=3567`, `missing_doc_links_actionable=4990`).
- Cola/WAF `only_linked_to_votes`: sin cambios (`missing_urls=1214`, `blocked_403_urls=508`, `blocked_500_urls=36`, `unknown_status_urls=297`, CSV `1215` lineas incl. cabecera).

## Calidad/limpieza semantica
- Sin regresion de extraccion (`downloaded_missing_extraction=0`, `extraction_needs_review=0`).
- Chequeo de ruido de navegacion Senado se mantiene en `0`.

## Estado
- Sprint cerrado como intento acotado reproducible con resultado no material (cohorte agotada para `archive fallback`).

## Evidencia
- `docs/etl/sprints/AI-OPS-323/evidence/initiative_doc_status_before_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/senado_waf_block_profile_before_.json`
- `docs/etl/sprints/AI-OPS-323/evidence/senado_manual_capture_validity_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/senado_enmiendas_index_status404_packet_summary_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/senado_retry_enmiendas_index_status404_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/initiative_doc_extractions_backfill_after_retry_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/initiative_doc_status_after_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/initiative_doc_status_delta_ai_ops_323_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/senado_waf_block_profile_after_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/senado_waf_block_profile_delta_ai_ops_323_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/senado_tail_actionable_delta_ai_ops_323_20260228T232721Z.json`
- `docs/etl/sprints/AI-OPS-323/evidence/senado_extraction_nav_noise_post_20260228T232721Z.json`
