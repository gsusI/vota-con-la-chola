# AI-OPS-362 — Senado `status=0` packet 50 (cuarta pasada refetch)

## Objetivo
Reducir el residual `status=0` tras AI-OPS-361 y confirmar delta neta en linked-to-votes.

## Resultado de retry
- `candidate_urls=50`
- `urls_to_fetch=50`
- `fetched_ok=50`
- `failures_total=0`
- runtime `10.53s`

Fuente: `docs/etl/sprints/AI-OPS-362/evidence/senado_status0_archive_retry_packet50_refetch_20260301T092037Z.json`

## Post-proceso
- `backfill_initiative_doc_extractions --only-missing`:
  - `seen=50`
  - `upserted=50`
  - `needs_review=0`

Fuente: `docs/etl/sprints/AI-OPS-362/evidence/initiative_doc_extractions_only_missing_after_status0_packet50_refetch_20260301T092037Z.json`

## Delta KPI
- `downloaded_doc_links`: `5102 -> 5152` (`+50`)
- `missing_doc_links_actionable`: `4260 -> 4210` (`-50`)
- `missing_urls` linked-to-votes: `484 -> 434` (`-50`)
- `unknown_status_urls`: `68 -> 18` (`-50`)
- `blocked_403_urls`: `64 -> 64` (`0`)

Fuentes:
- `docs/etl/sprints/AI-OPS-362/evidence/senado_status0_packet50_refetch_delta_ai_ops_362_20260301T092037Z.json`
- `docs/etl/sprints/AI-OPS-362/evidence/quality_initiatives_after_status0_packet50_refetch_20260301T092037Z.json`
- `docs/etl/sprints/AI-OPS-362/evidence/senado_waf_block_profile_after_status0_packet50_refetch_20260301T092037Z.json`

## Conclusión
Se cumple el DoD de reducción del residual `status=0` con conversión plena y sin regresión en `status=403`.
