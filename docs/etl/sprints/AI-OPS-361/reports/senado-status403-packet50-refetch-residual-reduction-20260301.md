# AI-OPS-361 — Senado `status=403` packet 50 (refetch)

## Objetivo
Reducir el residual `status=403` tras AI-OPS-360 y comprobar delta neta con una pasada dirigida en linked-to-votes.

## Resultado de retry
- `candidate_urls=50`
- `urls_to_fetch=50`
- `fetched_ok=49`
- `failures_total=1`
- runtime `20.54s`

Fuente: `docs/etl/sprints/AI-OPS-361/evidence/senado_status403_manual_cookie_archive_retry_packet50_refetch_20260301T091550Z.json`

## Post-proceso
- `backfill_initiative_doc_extractions --only-missing`:
  - `seen=49`
  - `upserted=49`
  - `needs_review=0`

Fuente: `docs/etl/sprints/AI-OPS-361/evidence/initiative_doc_extractions_only_missing_after_status403_packet50_refetch_20260301T091550Z.json`

## Delta KPI
- `downloaded_doc_links`: `5053 -> 5102` (`+49`)
- `missing_doc_links_actionable`: `4309 -> 4260` (`-49`)
- `missing_urls` linked-to-votes: `533 -> 484` (`-49`)
- `blocked_403_urls`: `114 -> 64` (`-50`)
- `unknown_status_urls`: `67 -> 68` (`+1`)

Fuentes:
- `docs/etl/sprints/AI-OPS-361/evidence/senado_status403_packet50_refetch_delta_ai_ops_361_20260301T091550Z.json`
- `docs/etl/sprints/AI-OPS-361/evidence/quality_initiatives_after_status403_packet50_refetch_20260301T091550Z.json`
- `docs/etl/sprints/AI-OPS-361/evidence/senado_waf_block_profile_after_status403_packet50_refetch_20260301T091550Z.json`

## Conclusión
Se cumple el DoD de reducción residual en `status=403` con delta material y sin regresión estructural (`needs_review=0`). La cola prioritaria se desplaza al tramo `status=0` (`unknown_status_urls=68`).
