# AI-OPS-356 — Senado `status=403` packet 25: conversión y cierre `zero_doc`

## Objetivo
Atacar el nuevo cuello de botella (`status=403` linked-to-votes) después del cierre de la lane `404`.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Cookie usada: `etl/data/raw/manual/senado_cookie_refresh_ai_ops_299_02_leg10_tipo610_20260301T075159Z.cookies.json`
- Packet exportado: `docs/etl/sprints/AI-OPS-356/exports/senado_status403_linked_packet25_20260301T085540Z.csv` (`25` URLs)
- Retry (`status=403`, `archive-fallback=403,404`, `retry-forbidden`) completado en `5.39s`

## Resultado del retry
- `candidate_urls=25`
- `urls_to_fetch=25`
- `fetched_ok=25`
- `failures_total=0`
- `archive_hits=0`

Fuente: `docs/etl/sprints/AI-OPS-356/evidence/senado_status403_manual_cookie_archive_retry_packet25_20260301T085540Z.json`

## Delta de cobertura
- `downloaded_doc_links`: `4828 -> 4853` (`+25`)
- `missing_doc_links_actionable`: `4535 -> 4509` (`-26`)
- `missing_urls` linked-to-votes: `759 -> 733` (`-26`)
- `blocked_403_urls`: `189 -> 164` (`-25`)
- `zero_doc_initiatives`: `5 -> 0` (`-5`)
- `linked_to_votes_with_downloaded_docs`: `746/751 -> 751/751`

Fuentes:
- `docs/etl/sprints/AI-OPS-356/evidence/quality_initiatives_before_status403_packet25_20260301T085540Z.json`
- `docs/etl/sprints/AI-OPS-356/evidence/quality_initiatives_after_status403_packet25_20260301T085540Z.json`
- `docs/etl/sprints/AI-OPS-356/evidence/senado_waf_block_profile_before_status403_packet25_20260301T085540Z.json`
- `docs/etl/sprints/AI-OPS-356/evidence/senado_waf_block_profile_after_status403_packet25_20260301T085540Z.json`
- `docs/etl/sprints/AI-OPS-356/evidence/senado_status403_conversion_delta_ai_ops_356_20260301T085540Z.json`

## Conclusión
La lane `status=403` convierte con throughput alto y deja cerrada la cola `zero_doc` en linked-to-votes.
