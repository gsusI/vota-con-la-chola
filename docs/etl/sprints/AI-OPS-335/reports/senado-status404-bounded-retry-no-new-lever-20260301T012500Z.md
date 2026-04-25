# AI-OPS-335 — Senado `status=404` retry acotado sin palanca nueva

Fecha (UTC): `2026-03-01T01:25:00Z`  
DB: `etl/data/staging/politicos-es.db`

## Objetivo
Ejecutar una iteración única y reproducible de la lane `status=404` (fila `837`) para intentar conversión de packet fresco a descargas efectivas, verificando explícitamente estado del lever de cookie.

## Ejecución
1. Baseline de estado y perfil WAF (`initiative_doc_status_before`, `senado_waf_block_profile_before`).
2. Matriz de lever de cookie con ficheros frescos y seed (`report_senado_cookie_lever_status`).
3. Export de pool accionable `status=404` linked-to-votes y packet canónico fresh (`retry_packet_only_dedup`).
4. Retry acotado (`limit=80`) con `--archive-fallback` y post-proceso de extracción/excerpt.
5. Medición de delta final (status global, tail accionable, perfil WAF).

## Resultado
- Packet lane: `pool_rows_total=802`, `fresh_rows_total=80`, `excluded_used_urls_total=160`.
- Retry lane: `candidate_urls=80`, `urls_to_fetch=80`, `fetched_ok=0`, `archive_hits=0`, `text_documents_upserted=0`.
- Lever cookie: `status=degraded`/`strict rc=4` para los candidatos evaluados; no se detecta palanca nueva utilizable.
- Delta final: sin cambio (`downloaded_doc_links=4414`, `missing_doc_links_actionable=4955`, `missing_urls=1179`, `blocked_403_urls=160`, `unknown_status_urls=217`).

## Evidencia
- `docs/etl/sprints/AI-OPS-335/evidence/senado_cookie_lever_status_matrix_20260301T012500Z.json`
- `docs/etl/sprints/AI-OPS-335/evidence/senado_status404_fresh_packet_summary_20260301T012500Z.json`
- `docs/etl/sprints/AI-OPS-335/evidence/senado_retry_status404_fresh_20260301T012500Z.json`
- `docs/etl/sprints/AI-OPS-335/evidence/initiative_doc_status_delta_ai_ops_335_20260301T012500Z.json`
- `docs/etl/sprints/AI-OPS-335/evidence/senado_tail_actionable_delta_ai_ops_335_20260301T012500Z.json`
- `docs/etl/sprints/AI-OPS-335/evidence/senado_waf_block_profile_after_20260301T012500Z.json`

## Decisión
La fila `837` permanece abierta: existe capacidad de packet pero la conversión sigue condicionada por palanca externa (cookie/sesión utilizable) y/o cobertura adicional de fallback archivístico.
