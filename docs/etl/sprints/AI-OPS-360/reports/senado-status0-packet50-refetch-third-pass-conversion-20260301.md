# AI-OPS-360 — Senado `status=0` packet 50 (tercera pasada refetch)

## Objetivo
Ejecutar una iteración adicional tras AI-OPS-359 para reducir el residual combinado, priorizando `status=0`.

## Resultado de retry
- `candidate_urls=50`
- `urls_to_fetch=50`
- `fetched_ok=50`
- `failures_total=0`
- runtime `5.59s`

Fuente: `docs/etl/sprints/AI-OPS-360/evidence/senado_status0_manual_cookie_archive_retry_packet50_refetch_20260301T091018Z.json`

## Post-proceso
- `backfill_initiative_doc_extractions --only-missing`:
  - `seen=50`
  - `upserted=50`
  - `needs_review=0`

Fuente: `docs/etl/sprints/AI-OPS-360/evidence/initiative_doc_extractions_only_missing_after_status0_packet50_refetch_20260301T091018Z.json`

## Delta KPI
- `downloaded_doc_links`: `5003 -> 5053` (`+50`)
- `missing_doc_links_actionable`: `4359 -> 4309` (`-50`)
- `missing_urls` linked-to-votes: `583 -> 533` (`-50`)
- `unknown_status_urls`: `117 -> 67` (`-50`)
- `blocked_403_urls`: `114 -> 114` (`0`)

Fuentes:
- `docs/etl/sprints/AI-OPS-360/evidence/senado_status0_packet50_refetch_third_pass_delta_ai_ops_360_20260301T091018Z.json`
- `docs/etl/sprints/AI-OPS-360/evidence/quality_initiatives_after_status0_packet50_refetch_20260301T091018Z.json`
- `docs/etl/sprints/AI-OPS-360/evidence/senado_waf_block_profile_after_status0_packet50_refetch_20260301T091018Z.json`

## Conclusión
Se cierra el objetivo combinado de reducción neta tras AI-OPS-359: la iteración logra delta material sin regresión en `status=403`.
