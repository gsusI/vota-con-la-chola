# AI-OPS-325 - Retry dirigido `status=403` con segundo packet fresco (`enmiendas/index`)

## Objetivo
Seguir cerrando la fila `822` con una cohorte fresca de `enmiendas/index.html` en `status=403`, evitando URLs ya reintentadas en AI-OPS-31x/32x/324 para minimizar loop no productivo.

## Ejecucion
1. Baseline
- `report_initiative_doc_status.py` (before)
- `report_senado_waf_block_profile.py --only-linked-to-votes` (before)
- `report_senado_manual_capture_validity.py --strict` (`status=degraded`, `strict_fail_reasons=[no_usable_capture]`, `rc=4`)

2. Seleccion de packet fresco
- Pool base: cola accionable `status=403`.
- Filtro: `enmiendas/index.html` excluyendo URLs ya presentes en packets AI-OPS-31x/32x/324.
- Resultado: `53` URLs / `53` iniciativas (`excluded_used_urls_total=590`).

3. Retry acotado
- `backfill-initiative-documents --doc-urls-file <fresh_packet> --retry-http-statuses 403 --archive-fallback --archive-fallback-http-statuses 403`
- Resultado:
  - `candidate_urls=53`, `urls_to_fetch=53`
  - `fetched_ok=15`, `archive_hits=15`, `archive_fetched_ok=15`, `text_documents_upserted=15`
  - `skipped_redundant_global_urls=13`, `failures=30`
  - `selected_scope_no_limit=true`

4. Post-proceso estructural
- `backfill_initiative_doc_extractions.py --only-missing --initiative-source-ids senado_iniciativas`
- Resultado: `seen=15`, `upserted=15`, `needs_review=0` (`title_hint_strong=12`, `keyword_sentence=3`).

## Delta medido
- Cobertura global iniciativas:
  - `downloaded_doc_links: 4392 -> 4407` (`+15`)
  - `missing_doc_links: 5161 -> 5146` (`-15`)
  - `missing_doc_links_actionable: 4977 -> 4962` (`-15`)
  - `effective_downloaded_doc_links_pct: 46.88 -> 47.04`
- Senado (`by_source`):
  - `downloaded_doc_links: 3580 -> 3595` (`+15`)
  - `missing_doc_links_actionable: 4977 -> 4962` (`-15`)
  - `downloaded_doc_links_pct: 40.96 -> 41.13`
- Cola/WAF `only_linked_to_votes`:
  - `missing_urls: 1201 -> 1186` (`-15`)
  - CSV cola (`incl. cabecera`): `1202 -> 1187`
  - `blocked_403_urls: 428 -> 375` (`-53`)
  - `blocked_500_urls` y `unknown_status_urls` sin cambio (`36/297`).

## Calidad/limpieza semantica
- Sin regresion:
  - `downloaded_missing_extraction=0`
  - `extraction_needs_review=0`
- Chequeo de ruido de navegacion Senado se mantiene en `0`.

## Estado
- `820/822` permanecen `PARTIAL` por bloqueo WAF residual, pero con mejora material acumulada en cobertura y cola accionable.
- Gap residual fresco queda concentrado en `ficopendataservlet` (`status=403/0/500`) para siguiente iteracion acotada.

## Evidencia
- `docs/etl/sprints/AI-OPS-325/evidence/initiative_doc_status_before_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/senado_waf_block_profile_before_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/senado_manual_capture_validity_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/senado_enmiendas_index_status403_fresh_packet_summary_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/senado_retry_enmiendas_index_status403_fresh_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/initiative_doc_extractions_backfill_after_retry_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/initiative_doc_status_after_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/initiative_doc_status_delta_ai_ops_325_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/senado_waf_block_profile_after_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/senado_waf_block_profile_delta_ai_ops_325_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/senado_tail_actionable_delta_ai_ops_325_20260228T234340Z.json`
- `docs/etl/sprints/AI-OPS-325/evidence/senado_extraction_nav_noise_post_20260228T234340Z.json`
