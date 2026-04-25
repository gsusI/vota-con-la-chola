# AI-OPS-324 - Retry dirigido `status=403` con packet fresco (`enmiendas/index`)

## Objetivo
Avanzar la fila `822` con una cohorte fresca (sin URLs ya reintentadas en AI-OPS-31x/32x) de `enmiendas/index.html` en `status=403` para recuperar docs por fallback historico.

## Ejecucion
1. Baseline
- `report_initiative_doc_status.py` (before)
- `report_senado_waf_block_profile.py --only-linked-to-votes` (before)
- `report_senado_manual_capture_validity.py --strict` (`status=degraded`, `strict_fail_reasons=[no_usable_capture]`, `rc=4`)

2. Seleccion de packet fresco
- Pool base: cola accionable `status=403`.
- Filtro: `enmiendas/index.html` excluyendo URLs ya presentes en packets AI-OPS-31x/32x.
- Resultado: `80` URLs / `80` iniciativas (`excluded_used_urls_total=510`).

3. Retry acotado
- `backfill-initiative-documents --doc-urls-file <fresh_packet> --retry-http-statuses 403 --archive-fallback --archive-fallback-http-statuses 403`
- Resultado:
  - `candidate_urls=80`, `urls_to_fetch=80`
  - `fetched_ok=13`, `archive_hits=13`, `archive_fetched_ok=13`, `text_documents_upserted=13`
  - `skipped_redundant_global_urls=42`, `failures=30`
  - `selected_scope_no_limit=true`

4. Post-proceso estructural
- `backfill_initiative_doc_extractions.py --only-missing --initiative-source-ids senado_iniciativas`
- Resultado: `seen=13`, `upserted=13`, `needs_review=0` (`title_hint_strong=12`, `keyword_sentence=1`).

## Delta medido
- Cobertura global iniciativas:
  - `downloaded_doc_links: 4379 -> 4392` (`+13`)
  - `missing_doc_links: 5174 -> 5161` (`-13`)
  - `missing_doc_links_actionable: 4990 -> 4977` (`-13`)
  - `effective_downloaded_doc_links_pct: 46.74 -> 46.88`
- Senado (`by_source`):
  - `downloaded_doc_links: 3567 -> 3580` (`+13`)
  - `missing_doc_links_actionable: 4990 -> 4977` (`-13`)
  - `downloaded_doc_links_pct: 40.81 -> 40.96`
- Cola/WAF `only_linked_to_votes`:
  - `missing_urls: 1214 -> 1201` (`-13`)
  - CSV cola (`incl. cabecera`): `1215 -> 1202`
  - `blocked_403_urls: 508 -> 428` (`-80`)
  - `blocked_500_urls` y `unknown_status_urls` sin cambio (`36/297`).

## Calidad/limpieza semantica
- Sin regresion:
  - `downloaded_missing_extraction=0`
  - `extraction_needs_review=0`
- Chequeo de ruido de navegacion Senado se mantiene en `0`.

## Estado
- `820/822` siguen `PARTIAL` por bloqueo WAF residual, pero con mejora material de cobertura y reduccion de cola accionable.

## Evidencia
- `docs/etl/sprints/AI-OPS-324/evidence/initiative_doc_status_before_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/senado_waf_block_profile_before_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/senado_manual_capture_validity_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/senado_enmiendas_index_status403_fresh_packet_summary_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/senado_retry_enmiendas_index_status403_fresh_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/initiative_doc_extractions_backfill_after_retry_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/initiative_doc_status_after_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/initiative_doc_status_delta_ai_ops_324_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/senado_waf_block_profile_after_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/senado_waf_block_profile_delta_ai_ops_324_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/senado_tail_actionable_delta_ai_ops_324_20260228T233500Z.json`
- `docs/etl/sprints/AI-OPS-324/evidence/senado_extraction_nav_noise_post_20260228T233500Z.json`
