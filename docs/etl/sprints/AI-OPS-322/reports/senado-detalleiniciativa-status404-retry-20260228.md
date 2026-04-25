# AI-OPS-322 - Retry dirigido `detalleiniciativa` (`status=404`) en cola Senado

## Objetivo
Continuar reducción de la fila `822` con una cohorte complementaria a AI-OPS-321: `detalleiniciativa/index.html` con `last_http_status=404` en scope `linked_to_votes`.

## Ejecución
1. Baseline
- `report_initiative_doc_status.py` (before)
- `report_senado_waf_block_profile.py --only-linked-to-votes` (before)
- `report_senado_manual_capture_validity.py --strict` (`status=degraded`, `strict_fail_reasons=[no_usable_capture]`, `rc=4`)

2. Packet dirigido
- `senado_detalleiniciativa_status404_packet`: `69` URLs / `69` iniciativas.

3. Retry acotado (sin cookie usable)
- `backfill-initiative-documents --doc-urls-file <packet> --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404`
- Resultado:
  - `candidate_urls=69`, `urls_to_fetch=69`
  - `fetched_ok=6`, `archive_hits=6`, `archive_fetched_ok=6`, `text_documents_upserted=6`
  - `selected_scope_no_limit=true`

4. Post-proceso de estructuración
- `backfill_initiative_doc_extractions.py --only-missing --initiative-source-ids senado_iniciativas`
- Resultado: `seen=6`, `upserted=6`, `needs_review=0`, `by_method.title_hint_strong=6`.

## Delta medido
- Cobertura global iniciativas:
  - `downloaded_doc_links: 4373 -> 4379` (`+6`)
  - `missing_doc_links: 5180 -> 5174` (`-6`)
  - `missing_doc_links_actionable: 4996 -> 4990` (`-6`)
  - `effective_downloaded_doc_links_pct: 46.68 -> 46.74`
- Senado (`by_source`):
  - `downloaded_doc_links: 3561 -> 3567` (`+6`)
  - `missing_doc_links_actionable: 4996 -> 4990` (`-6`)
  - `effective_downloaded_doc_links_pct: 41.62 -> 41.69`
- Cola/WAF `only_linked_to_votes`:
  - `missing_urls: 1220 -> 1214` (`-6`)
  - CSV cola (`incl. header`): `1221 -> 1215`
  - `blocked_403_urls`, `blocked_500_urls`, `unknown_status_urls` sin cambio (`508/36/297`).

## Calidad/limpieza semántica
- Sin regresión de extracción:
  - `downloaded_missing_extraction=0`
  - `extraction_needs_review=0`
- Chequeo de ruido de navegación Senado se mantiene en `0`.

## Validación
- `python3 scripts/e2e_tracker_status.py ...` -> `mismatches=0`, `done_zero_real=0`

## Evidencia
- `docs/etl/sprints/AI-OPS-322/evidence/initiative_doc_status_before_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/senado_waf_block_profile_before_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/senado_manual_capture_validity_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/senado_detalleiniciativa_status404_packet_summary_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/senado_retry_detalleiniciativa_status404_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/initiative_doc_extractions_backfill_after_retry_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/initiative_doc_status_after_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/initiative_doc_status_delta_ai_ops_322_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/senado_waf_block_profile_after_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/senado_waf_block_profile_delta_ai_ops_322_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/senado_tail_actionable_delta_ai_ops_322_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/senado_extraction_nav_noise_post_20260228T232136Z.json`
- `docs/etl/sprints/AI-OPS-322/evidence/tracker_status_20260228T232136Z.log`

## Estado
- `820/822`: continúan `PARTIAL`, con nueva reducción material de cola y mantenimiento de calidad semántica.
