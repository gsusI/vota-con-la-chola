# AI-OPS-359 — Senado `status=0` packet 50 (segunda pasada refetch)

## Objetivo
Reducir el residual `status=0` (`unknown_status_urls`) tras la primera pasada de AI-OPS-358.

## Ejecución
- Cohorte exportada: `50` URLs (`linked_to_votes`, `status=0`).
- Retry dirigido con patrón `refetch`:
  - `candidate_urls=50`
  - `urls_to_fetch=50`
  - `fetched_ok=50`
  - `failures_total=0`
  - runtime `6.27s`

Fuente: `docs/etl/sprints/AI-OPS-359/evidence/senado_status0_manual_cookie_archive_retry_packet50_refetch_20260301T090541Z.json`

## Post-proceso
- `backfill_initiative_doc_extractions --only-missing`:
  - `seen=50`
  - `upserted=50`
  - `needs_review=0`

Fuente: `docs/etl/sprints/AI-OPS-359/evidence/initiative_doc_extractions_only_missing_after_status0_packet50_refetch_20260301T090541Z.json`

## Delta KPI
- `downloaded_doc_links`: `4953 -> 5003` (`+50`)
- `missing_doc_links_actionable`: `4409 -> 4359` (`-50`)
- `missing_urls` linked-to-votes: `633 -> 583` (`-50`)
- `unknown_status_urls`: `167 -> 117` (`-50`)
- `blocked_403_urls`: `114 -> 114` (`0`)

Fuente: `docs/etl/sprints/AI-OPS-359/evidence/senado_status0_packet50_refetch_second_pass_delta_ai_ops_359_20260301T090541Z.json`

## Conclusión
La segunda pasada `status=0` mantiene conversión plena con delta material y cierra el objetivo de reducción residual abierto en AI-OPS-358.
