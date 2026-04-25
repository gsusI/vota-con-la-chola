# AI-OPS-338 — Senado `status=404` retry ancho (iteración 3) con conversión parcial

Fecha (UTC): `2026-03-01T01:47:59Z`  
DB: `etl/data/staging/politicos-es.db`

## Objetivo
Continuar reducción de cola accionable `status=404` con un único burst reproducible de mayor amplitud (`240` filas) manteniendo cobertura semántica en verde.

## Ejecución
1. Baseline de estado iniciativas + perfil WAF + cola accionable linked-to-votes.
2. Validación de cookie lever (continúa `degraded` por `cookie_file_stale`).
3. Export de pool `status=404` y selección de packet canónico (`retry_packet_only_dedup`, `max_rows=240`).
4. Retry único con `--archive-fallback`.
5. Reconciliación semántica (`backfill_initiative_doc_extractions --only-missing`, `backfill_initiative_doc_excerpts`) y medición final.

## Resultado
- Packet lane: `pool_rows_total=798`, `used_urls_total=616`, `excluded_used_urls_total=556`, `fresh_rows_total=240`.
- Retry lane: `candidate_urls=240`, `urls_to_fetch=240`, `fetched_ok=2`, `archive_hits=2`, `text_documents_upserted=2`.
- Post-proceso semántico: `seen=2`, `upserted=2`, `needs_review=0`; excerpt/extracción descargada sigue en `100%`.

### Delta medido
- `downloaded_doc_links`: `4418 -> 4420` (`+2`)
- `missing_doc_links`: `5135 -> 5133` (`-2`)
- `missing_doc_links_actionable`: `4951 -> 4949` (`-2`)
- `effective_downloaded_doc_links_pct`: `47.16 -> 47.18` (`+0.02`)
- Senado `status=404`: `877 -> 875` (`-2`)
- Tail accionable linked-to-votes: `1175 -> 1173` filas CSV (`-2` URLs)
- Perfil WAF linked-to-votes: `missing_urls 1175 -> 1173` (`-2`), `blocked_403_urls=160` estable, `unknown_status_urls=217` estable.

## Evidencia
- `docs/etl/sprints/AI-OPS-338/evidence/senado_status404_fresh_packet_summary_20260301T014759Z.json`
- `docs/etl/sprints/AI-OPS-338/evidence/senado_retry_status404_fresh_20260301T014759Z.json`
- `docs/etl/sprints/AI-OPS-338/evidence/initiative_doc_status_delta_ai_ops_338_20260301T014759Z.json`
- `docs/etl/sprints/AI-OPS-338/evidence/senado_tail_actionable_delta_ai_ops_338_20260301T014759Z.json`
- `docs/etl/sprints/AI-OPS-338/evidence/senado_waf_block_profile_delta_ai_ops_338_20260301T014759Z.json`
- `docs/etl/sprints/AI-OPS-338/evidence/senado_cookie_lever_status_20260301T014759Z.json`

## Decisión
La fila `837` sigue abierta por dependencia externa de palanca de sesión, pero esta iteración mantiene avance material reproducible (`+2`) sin degradar calidad de datos estructurados.
