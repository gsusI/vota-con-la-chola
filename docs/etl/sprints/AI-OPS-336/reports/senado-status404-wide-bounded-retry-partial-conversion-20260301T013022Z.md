# AI-OPS-336 — Senado `status=404` retry ancho con conversión parcial

Fecha (UTC): `2026-03-01T01:30:22Z`  
DB: `etl/data/staging/politicos-es.db`

## Objetivo
Repetir la lane `status=404` con un packet fresco más ancho (`max_rows=160`) para buscar conversión efectiva de descarga en ausencia de palanca nueva de cookie.

## Ejecución
1. Baseline de estado (`report_initiative_doc_status`) y perfil WAF (`report_senado_waf_block_profile`).
2. Export de pool accionable `status=404` linked-to-votes (`802` filas).
3. Selección canónica de packet fresh con dedupe por packets previos (`retry_packet_only_dedup`, `max_rows=160`).
4. Retry acotado con `--archive-fallback` + post-proceso (`backfill_initiative_doc_extractions --only-missing`, `backfill_initiative_doc_excerpts`).
5. Medición de delta final (`initiative_doc_status`, `tail_actionable`, `waf_block_profile`).

## Resultado
- Packet lane: `pool_rows_total=802`, `used_urls_total=296`, `excluded_used_urls_total=240`, `fresh_rows_total=160`.
- Retry lane: `candidate_urls=160`, `urls_to_fetch=160`, `archive_lookup_attempted=160`, `archive_hits=3`, `fetched_ok=3`, `text_documents_upserted=3`.
- Post-proceso semántico: `seen=3`, `upserted=3`, `needs_review=0`, excerpt/extracción descargada mantiene cobertura `100%`.

### Delta medido
- `downloaded_doc_links`: `4414 -> 4417` (`+3`)
- `missing_doc_links`: `5139 -> 5136` (`-3`)
- `missing_doc_links_actionable`: `4955 -> 4952` (`-3`)
- `effective_downloaded_doc_links_pct`: `47.11 -> 47.14` (`+0.03`)
- Senado `status=404` residual: `881 -> 878` (`-3`)
- Tail accionable linked-to-votes: `1180 -> 1177` filas CSV (`-3` URLs)
- Perfil WAF linked-to-votes: `missing_urls 1179 -> 1176` (`-3`), `blocked_403_urls=160` estable, `unknown_status_urls=217` estable.

## Evidencia
- `docs/etl/sprints/AI-OPS-336/evidence/senado_status404_fresh_packet_summary_20260301T013022Z.json`
- `docs/etl/sprints/AI-OPS-336/evidence/senado_retry_status404_fresh_20260301T013022Z.json`
- `docs/etl/sprints/AI-OPS-336/evidence/initiative_doc_status_delta_ai_ops_336_20260301T013022Z.json`
- `docs/etl/sprints/AI-OPS-336/evidence/senado_tail_actionable_delta_ai_ops_336_20260301T013022Z.json`
- `docs/etl/sprints/AI-OPS-336/evidence/senado_waf_block_profile_delta_ai_ops_336_20260301T013022Z.json`
- `docs/etl/sprints/AI-OPS-336/evidence/tracker_status_20260301T013022Z.log`
- `docs/etl/sprints/AI-OPS-336/evidence/e2e_tracker_status_20260301T013022Z.log`

## Decisión
La fila `837` permanece `TODO` pero con avance material (`+3`) y validación de que la lane `status=404` aún tiene capacidad de conversión parcial bajo retry acotado con fallback archivístico.
