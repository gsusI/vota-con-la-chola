# AI-OPS-321 - Retry dirigido `detalleiniciativa` (`status=403`) en cola Senado

## Objetivo
Continuar cierre de `822` con una cohorte distinta a AI-OPS-320: URLs `detalleiniciativa/index.html` con `last_http_status=403` en scope `only_linked_to_votes`.

## Ejecución
1. Baseline
- `report_initiative_doc_status.py` (before)
- `report_senado_waf_block_profile.py --only-linked-to-votes` (before)
- `report_senado_manual_capture_validity.py --strict` (`status=degraded`, `strict_fail_reasons=[no_usable_capture]`, `rc=4`)

2. Packet dirigido
- `senado_detalleiniciativa_status403_packet`: `78` URLs / `78` iniciativas.

3. Retry acotado (sin cookie usable)
- `backfill-initiative-documents --doc-urls-file <packet> --retry-http-statuses 403 --archive-fallback --archive-fallback-http-statuses 403`
- Resultado:
  - `candidate_urls=78`, `urls_to_fetch=78`
  - `fetched_ok=23`, `archive_hits=23`, `archive_fetched_ok=23`, `text_documents_upserted=23`
  - `selected_scope_no_limit=true`

4. Post-proceso de estructuración
- `backfill_initiative_doc_extractions.py --only-missing --initiative-source-ids senado_iniciativas`
- Resultado: `seen=23`, `upserted=23`, `needs_review=0`, `by_method.title_hint_strong=23`.

## Delta medido
- Cobertura global iniciativas:
  - `downloaded_doc_links: 4350 -> 4373` (`+23`)
  - `missing_doc_links: 5203 -> 5180` (`-23`)
  - `missing_doc_links_actionable: 5019 -> 4996` (`-23`)
  - `effective_downloaded_doc_links_pct: 46.43 -> 46.68`
- Senado (`by_source`):
  - `downloaded_doc_links: 3538 -> 3561` (`+23`)
  - `missing_doc_links_actionable: 5019 -> 4996` (`-23`)
  - `effective_downloaded_doc_links_pct: 41.35 -> 41.62`
- Cola/WAF `only_linked_to_votes`:
  - `missing_urls: 1243 -> 1220` (`-23`)
  - `blocked_403_urls: 586 -> 508` (`-78`)
  - CSV cola (`incl. header`): `1244 -> 1221`

## Calidad/limpieza semántica
- No hay regresión de extracción:
  - `downloaded_missing_extraction=0`
  - `extraction_needs_review=0`
- Chequeo de ruido de navegación Senado tras el slice: `noise_rows_total=0`.

## Validación
- `python3 scripts/e2e_tracker_status.py ...` -> `mismatches=0`, `done_zero_real=0`

## Evidencia
- `docs/etl/sprints/AI-OPS-321/evidence/initiative_doc_status_before_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/senado_waf_block_profile_before_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/senado_manual_capture_validity_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/senado_detalleiniciativa_status403_packet_summary_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/senado_retry_detalleiniciativa_status403_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/initiative_doc_extractions_backfill_after_retry_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/initiative_doc_status_after_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/initiative_doc_status_delta_ai_ops_321_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/senado_waf_block_profile_after_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/senado_waf_block_profile_delta_ai_ops_321_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/senado_tail_actionable_delta_ai_ops_321_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/senado_extraction_nav_noise_post_20260228T231413Z.json`
- `docs/etl/sprints/AI-OPS-321/evidence/tracker_status_20260228T231413Z.log`

## Estado
- `820/822`: continúan `PARTIAL`, pero con mejora material significativa de descarga/cola en esta iteración.
