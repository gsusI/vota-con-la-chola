# AI-OPS-326 - Retry dirigido `ficopendataservlet` (`status=403/500`) con cohorte fresca

## Objetivo
Avanzar la fila `822` sobre la lane residual `ficopendataservlet` con un intento acotado y reproducible, priorizando URLs frescas no reintentadas en AI-OPS-31x/32x/324/325.

## Ejecucion
1. Baseline
- `report_initiative_doc_status.py` (before)
- `report_senado_waf_block_profile.py --only-linked-to-votes` (before)
- `report_senado_manual_capture_validity.py --strict` (`status=degraded`, `strict_fail_reasons=[no_usable_capture]`, `rc=4`)

2. Seleccion de packet fresco
- Pool base: cola accionable post-AI-OPS-325.
- Filtro: `doc_url LIKE %ficopendataservlet%`, `status in (403,500)` excluyendo URLs ya usadas en packets previos.
- Resultado: `80` URLs / `80` iniciativas (`status_buckets: 500=36, 403=44`, `excluded_used_urls_total=643`).

3. Retry acotado
- `backfill-initiative-documents --doc-urls-file <fresh_packet> --retry-http-statuses 403,500 --archive-fallback --archive-fallback-http-statuses 403,500`
- Resultado:
  - `candidate_urls=80`, `urls_to_fetch=80`
  - `fetched_ok=3`, `archive_hits=3`, `archive_fetched_ok=3`, `text_documents_upserted=3`
  - `skipped_redundant_global_urls=42`, `failures=30`
  - `selected_scope_no_limit=true`

4. Post-proceso estructural
- `backfill_initiative_doc_extractions.py --only-missing --initiative-source-ids senado_iniciativas`
- Resultado: `seen=3`, `upserted=3`, `needs_review=0` (`title_fallback_strong=3`).

5. Cierre de calidad local (excerpt)
- Se detecta regresion puntual post-retry: `downloaded_missing_excerpt=3`.
- Se aplica `backfill_initiative_doc_excerpts.py` sobre `senado_iniciativas`.
- Resultado: `seen=3`, `updated=3`; estado final vuelve a `downloaded_missing_excerpt=0` y `excerpt_coverage_pct=100.0`.

## Delta medido
- Cobertura global iniciativas:
  - `downloaded_doc_links: 4407 -> 4410` (`+3`)
  - `missing_doc_links: 5146 -> 5143` (`-3`)
  - `missing_doc_links_actionable: 4962 -> 4959` (`-3`)
  - `effective_downloaded_doc_links_pct: 47.04 -> 47.07`
- Senado (`by_source`):
  - `downloaded_doc_links: 3595 -> 3598` (`+3`)
  - `missing_doc_links_actionable: 4962 -> 4959` (`-3`)
  - `downloaded_doc_links_pct: 41.13 -> 41.16`
- Cola/WAF `only_linked_to_votes`:
  - `missing_urls: 1186 -> 1183` (`-3`)
  - CSV cola (`incl. cabecera`): `1187 -> 1184`
  - `blocked_403_urls: 375 -> 331` (`-44`)
  - `blocked_500_urls: 36 -> 0` (`-36`)
  - `unknown_status_urls` sin cambio (`297`).

## Calidad/limpieza semantica
- Estado final en verde:
  - `downloaded_missing_extraction=0`
  - `extraction_needs_review=0`
  - `downloaded_missing_excerpt=0`
- Chequeo de ruido de navegacion Senado se mantiene en `0`.

## Estado
- `820/822` siguen `PARTIAL` por bloqueo WAF residual, con mejora material incremental en la lane `ficopendataservlet`.
- Gap residual operativo queda concentrado en `status=403` remanente y `unknown_status_urls=297`.

## Evidencia
- `docs/etl/sprints/AI-OPS-326/evidence/initiative_doc_status_before_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/senado_waf_block_profile_before_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/senado_manual_capture_validity_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/senado_ficopendataservlet_status_0_403_500_fresh_packet_summary_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/senado_retry_ficopendataservlet_status_403_500_fresh_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/initiative_doc_extractions_backfill_after_retry_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/initiative_doc_excerpts_backfill_after_retry_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/initiative_doc_status_after_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/initiative_doc_status_delta_ai_ops_326_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/senado_waf_block_profile_after_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/senado_waf_block_profile_delta_ai_ops_326_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/senado_tail_actionable_delta_ai_ops_326_20260228T235030Z.json`
- `docs/etl/sprints/AI-OPS-326/evidence/senado_extraction_nav_noise_post_20260228T235030Z.json`
