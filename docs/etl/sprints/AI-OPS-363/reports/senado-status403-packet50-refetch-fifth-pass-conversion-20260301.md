# AI-OPS-363 — Senado `status=403` packet 50 (quinta pasada refetch)

## Objetivo
Reducir el residual `status=403` tras AI-OPS-362 y validar cierre de cola WAF crítica en linked-to-votes.

## Resultado de retry
- `candidate_urls=50`
- `urls_to_fetch=50`
- `fetched_ok=50`
- `failures_total=0`
- runtime `5.93s`

Fuente: `docs/etl/sprints/AI-OPS-363/evidence/senado_status403_archive_retry_packet50_refetch_20260301T092434Z.json`

## Post-proceso
- `backfill_initiative_doc_extractions --only-missing`:
  - `seen=50`
  - `upserted=50`
  - `needs_review=0`

Fuente: `docs/etl/sprints/AI-OPS-363/evidence/initiative_doc_extractions_only_missing_after_status403_packet50_refetch_20260301T092434Z.json`

## Delta KPI
- `downloaded_doc_links`: `5152 -> 5202` (`+50`)
- `missing_doc_links_actionable`: `4210 -> 4160` (`-50`)
- `missing_urls` linked-to-votes: `434 -> 384` (`-50`)
- `blocked_403_urls`: `64 -> 14` (`-50`)
- `unknown_status_urls`: `18 -> 18` (`0`)

Fuentes:
- `docs/etl/sprints/AI-OPS-363/evidence/senado_status403_packet50_refetch_delta_ai_ops_363_20260301T092434Z.json`
- `docs/etl/sprints/AI-OPS-363/evidence/quality_initiatives_after_status403_packet50_refetch_20260301T092434Z.json`
- `docs/etl/sprints/AI-OPS-363/evidence/senado_waf_block_profile_after_status403_packet50_refetch_20260301T092434Z.json`

## Conclusión
Se cumple el DoD con reducción material del bucket `status=403`; el residual operativo pasa a tramo final (`status=0` y `status=403` de baja magnitud).
