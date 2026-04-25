# AI-OPS-333 - Retry acotado `status=404` con dedupe canónico (sin nueva palanca)

## Objetivo
Continuar el cierre de `820/822/837` con una iteración reproducible de scraping/procesado en Senado, ejecutando **una sola** corrida de red en la lane `status=404` bajo contrato `retry_packet_only_dedup`.

## Ejecución
1. Baseline (`initiative_doc_status` + `senado_waf_block_profile`) sobre `etl/data/staging/politicos-es.db`.
2. Gate de palanca manual/cookie:
- `report_senado_cookie_lever_status --strict`: `status=degraded`, `strict rc=4`, `strict_fail_reasons=[cookie_file_stale]`.
3. Export de pool accionable Senado `status=404`:
- `pool_rows_total=802`.
4. Packetización canónica (`retry_packet_only_dedup`):
- `used_packet_files_total=14`, `used_urls_total=702`, `excluded_used_urls_total=152`, `fresh_rows_total=80`, `status=ok`.
5. Único retry de red del sprint (lane `status=404`, packet 80 filas):
- `candidate_urls=56`, `urls_to_fetch=56`, `skipped_redundant_global_urls=40`.
- `fetched_ok=0`, `archive_hits=0`, `archive_fetched_ok=0`, `text_documents_upserted=0`.
- `failures_count=30`.
6. Post-proceso local (`extractions/excerpts`): sin nuevos pendientes ni regresiones (`seen/upserted/updated=0`).

## Delta medido (before -> after)
- `downloaded_doc_links`: `0` delta (`4414 -> 4414`)
- `missing_doc_links`: `0` delta (`5139 -> 5139`)
- `missing_doc_links_actionable`: `0` delta (`4955 -> 4955`)
- `effective_downloaded_doc_links_pct`: `0` delta (`47.11 -> 47.11`)
- WAF linked-to-votes: sin delta (`missing_urls=1179`, `blocked_403_urls=160`, `unknown_status_urls=217`).

## Conclusión
- Se mantiene disciplina anti-loop (un único retry de red sin nueva palanca en este sprint) y trazabilidad completa de la lane `status=404`.
- No hubo recuperación de descarga; el bloqueo persiste con cookie stale (`no_new_lever`).
- Queda priorizada la necesidad de palanca nueva verificable (cookie fresca o alternativa reproducible) para convertir packet fresco en cobertura real.

## Evidencia
- `docs/etl/sprints/AI-OPS-333/evidence/senado_cookie_lever_status_20260301T010746Z.json`
- `docs/etl/sprints/AI-OPS-333/evidence/senado_cookie_lever_status_20260301T010746Z.rc`
- `docs/etl/sprints/AI-OPS-333/evidence/senado_status404_fresh_packet_summary_20260301T010746Z.json`
- `docs/etl/sprints/AI-OPS-333/evidence/senado_retry_status404_fresh_20260301T010746Z.json`
- `docs/etl/sprints/AI-OPS-333/evidence/initiative_doc_status_delta_ai_ops_333_20260301T010746Z.json`
- `docs/etl/sprints/AI-OPS-333/evidence/initiative_doc_status_after_20260301T010746Z.json`
- `docs/etl/sprints/AI-OPS-333/evidence/senado_waf_block_profile_after_20260301T010746Z.json`
