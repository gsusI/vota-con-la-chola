# AI-OPS-357 — Senado `status=403` packet 50 (reducción del residual)

## Objetivo
Escalar la lane `status=403` tras la conversión inicial de AI-OPS-356 para recortar el residual operativo (`blocked_403_urls` y `missing_urls`).

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Cookie usada: `etl/data/raw/manual/senado_cookie_refresh_ai_ops_299_02_leg10_tipo610_20260301T075159Z.cookies.json`
- Packet exportado: `docs/etl/sprints/AI-OPS-357/exports/senado_status403_linked_packet50_20260301T085854Z.csv` (`50` URLs)
- Retry (`status=403`, `archive-fallback=403,404`) completado en `9.48s`

## Resultado del retry
- `candidate_urls=50`
- `urls_to_fetch=50`
- `fetched_ok=50`
- `failures_total=0`
- `archive_hits=0`

Fuente: `docs/etl/sprints/AI-OPS-357/evidence/senado_status403_manual_cookie_archive_retry_packet50_20260301T085854Z.json`

## Post-proceso
- `backfill_initiative_doc_extractions --only-missing`:
  - `seen=99`
  - `upserted=99`
  - `needs_review=0`

Fuente: `docs/etl/sprints/AI-OPS-357/evidence/initiative_doc_extractions_only_missing_after_status403_packet50_20260301T085854Z.json`

## Delta de cobertura
- `downloaded_doc_links`: `4853 -> 4903` (`+50`)
- `missing_doc_links_actionable`: `4509 -> 4459` (`-50`)
- `missing_urls` linked-to-votes: `733 -> 683` (`-50`)
- `blocked_403_urls`: `164 -> 114` (`-50`)
- `zero_doc_initiatives`: `0 -> 0`
- `linked_to_votes_with_downloaded_docs`: `751/751` (sin cambio)

Fuentes:
- `docs/etl/sprints/AI-OPS-357/evidence/quality_initiatives_before_status403_packet50_20260301T085854Z.json`
- `docs/etl/sprints/AI-OPS-357/evidence/quality_initiatives_after_status403_packet50_20260301T085854Z.json`
- `docs/etl/sprints/AI-OPS-357/evidence/senado_waf_block_profile_before_status403_packet50_20260301T085854Z.json`
- `docs/etl/sprints/AI-OPS-357/evidence/senado_waf_block_profile_after_status403_packet50_20260301T085854Z.json`
- `docs/etl/sprints/AI-OPS-357/evidence/senado_status403_packet50_conversion_delta_ai_ops_357_20260301T085854Z.json`

## Conclusión
Se cumple el DoD del slice (`runtime_guard_ok`, `delta_target_met`, `postprocess_ok`) y la lane `status=403` mantiene conversión alta al escalar el packet.
