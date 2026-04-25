# AI-OPS-358 — Senado `status=0` packet 50 (refetch) con conversión

## Objetivo
Reducir el bucket `unknown_status_urls` (`status=0`) en linked-to-votes con packet `50`.

## Iteración y ajuste
- Intento inicial (filtro `--retry-http-statuses 0`, sin `--refetch-existing`) no produjo delta (`urls_to_fetch=0`, `skipped_existing=50`, `skipped_retry_http_statuses=50`).
- Ajuste aplicado: misma cohorte, activando `--refetch-existing` y quitando el filtro `--retry-http-statuses` para evitar descarte total por snapshot incompleto.

## Resultado del intento corregido
- `candidate_urls=50`
- `urls_to_fetch=50`
- `fetched_ok=50`
- `failures_total=0`
- runtime `5.81s`

Fuente: `docs/etl/sprints/AI-OPS-358/evidence/senado_status0_manual_cookie_archive_retry_packet50_refetch_20260301T090203Z.json`

## Post-proceso
- `backfill_initiative_doc_extractions --only-missing`:
  - `seen=50`
  - `upserted=50`
  - `needs_review=0`

Fuente: `docs/etl/sprints/AI-OPS-358/evidence/initiative_doc_extractions_only_missing_after_status0_packet50_refetch_20260301T090203Z.json`

## Delta de cobertura
- `downloaded_doc_links`: `4903 -> 4953` (`+50`)
- `missing_doc_links_actionable`: `4459 -> 4409` (`-50`)
- `missing_urls` linked-to-votes: `683 -> 633` (`-50`)
- `unknown_status_urls`: `217 -> 167` (`-50`)
- `blocked_403_urls`: `114 -> 114` (`0`)

Fuentes:
- `docs/etl/sprints/AI-OPS-358/evidence/quality_initiatives_before_status0_packet50_20260301T090203Z.json`
- `docs/etl/sprints/AI-OPS-358/evidence/quality_initiatives_after_status0_packet50_refetch_20260301T090203Z.json`
- `docs/etl/sprints/AI-OPS-358/evidence/senado_waf_block_profile_before_status0_packet50_20260301T090203Z.json`
- `docs/etl/sprints/AI-OPS-358/evidence/senado_waf_block_profile_after_status0_packet50_refetch_20260301T090203Z.json`
- `docs/etl/sprints/AI-OPS-358/evidence/senado_status0_packet50_refetch_delta_ai_ops_358_20260301T090203Z.json`

## Conclusión
La lane `status=0` queda operativa con patrón `refetch` y entrega reducción material del bucket `unknown` en una sola corrida.
