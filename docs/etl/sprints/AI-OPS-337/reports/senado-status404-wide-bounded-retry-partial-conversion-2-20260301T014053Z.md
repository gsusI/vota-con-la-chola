# AI-OPS-337 — Senado `status=404` retry ancho (iteración 2) con conversión parcial

Fecha (UTC): `2026-03-01T01:40:53Z`  
DB: `etl/data/staging/politicos-es.db`

## Objetivo
Ejecutar una nueva iteración acotada en lane `status=404` con packet fresco (`160` filas) para seguir reduciendo cola accionable y aumentar cobertura descargada.

## Ejecución
1. Baseline de estado iniciativas, perfil WAF y cola accionable linked-to-votes.
2. Verificación de cookie lever (`strict` degradado por stale).
3. Export de pool `status=404` y packet canónico fresh con dedupe (`retry_packet_only_dedup`, `max_rows=160`).
4. Retry único con `--archive-fallback`.
5. Reconciliación semántica (`backfill_initiative_doc_extractions --only-missing`, `backfill_initiative_doc_excerpts`) y medición final.

## Resultado
- Packet lane: `pool_rows_total=799`, `used_urls_total=456`, `excluded_used_urls_total=397`, `fresh_rows_total=160`.
- Retry lane: `candidate_urls=160`, `urls_to_fetch=160`, `fetched_ok=1`, `archive_hits=1`, `text_documents_upserted=1`.
- Post-proceso semántico: `seen=1`, `upserted=1`, `needs_review=0`; excerpt/extracción en descargados se mantiene al `100%`.

### Delta medido
- `downloaded_doc_links`: `4417 -> 4418` (`+1`)
- `missing_doc_links`: `5136 -> 5135` (`-1`)
- `missing_doc_links_actionable`: `4952 -> 4951` (`-1`)
- `effective_downloaded_doc_links_pct`: `47.14 -> 47.16` (`+0.02`)
- Senado `status=404`: `878 -> 877` (`-1`)
- Tail accionable linked-to-votes: `1176 -> 1175` filas CSV (`-1` URL)
- Perfil WAF linked-to-votes: `missing_urls 1176 -> 1175` (`-1`), `blocked_403_urls=160` estable, `unknown_status_urls=217` estable.

## Evidencia
- `docs/etl/sprints/AI-OPS-337/evidence/senado_status404_fresh_packet_summary_20260301T014053Z.json`
- `docs/etl/sprints/AI-OPS-337/evidence/senado_retry_status404_fresh_20260301T014053Z.json`
- `docs/etl/sprints/AI-OPS-337/evidence/initiative_doc_status_delta_ai_ops_337_20260301T014053Z.json`
- `docs/etl/sprints/AI-OPS-337/evidence/senado_tail_actionable_delta_ai_ops_337_20260301T014053Z.json`
- `docs/etl/sprints/AI-OPS-337/evidence/senado_waf_block_profile_delta_ai_ops_337_20260301T014053Z.json`
- `docs/etl/sprints/AI-OPS-337/evidence/senado_cookie_lever_status_20260301T014053Z.json`

## Decisión
La fila `837` permanece abierta, pero se confirma conversión parcial reproducible adicional en la lane `status=404` sin degradar calidad semántica.
