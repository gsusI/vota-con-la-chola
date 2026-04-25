# AI-OPS-364 — Senado `status=404` packet 50 (no_new_lever)

## Objetivo
Atacar el nuevo residual dominante `status=404` tras AI-OPS-363 y medir delta neta en linked-to-votes.

## Resultado de retry
- `candidate_urls=18`
- `urls_to_fetch=18`
- `fetched_ok=0`
- `failures_total=18`
- `archive_hits=0`
- runtime `271.83s`

Fuente: `docs/etl/sprints/AI-OPS-364/evidence/senado_status404_archive_retry_packet50_refetch_20260301T092750Z.json`

## Diagnóstico de bloqueo
- Patrón dominante de fallo: `archive fallback: no snapshot candidates`
- Evidencia estructurada del gap archivístico: `archive_no_snapshot_failures_total=18`, `unique_urls_total=18`
- URLs afectadas concentradas en `detalleiniciativa` (`leg10 tipo610`)

Fuentes:
- `docs/etl/sprints/AI-OPS-364/evidence/senado_status404_archive_retry_packet50_refetch_20260301T092750Z.json`
- `docs/etl/sprints/AI-OPS-364/evidence/senado_archive_gap_urls_20260301T092750Z.json`
- `docs/etl/sprints/AI-OPS-364/exports/senado_archive_gap_urls_20260301T092750Z.csv`

## Delta KPI
- `downloaded_doc_links`: `5202 -> 5202` (`0`)
- `missing_doc_links_actionable`: `4160 -> 4160` (`0`)
- `missing_urls` linked-to-votes: `384 -> 384` (`0`)
- `unknown_status_urls`: `18 -> 18` (`0`)
- `blocked_403_urls`: `14 -> 14` (`0`)

Fuentes:
- `docs/etl/sprints/AI-OPS-364/evidence/senado_status404_packet50_refetch_delta_ai_ops_364_20260301T092750Z.json`
- `docs/etl/sprints/AI-OPS-364/evidence/quality_initiatives_after_status404_packet50_refetch_20260301T092750Z.json`
- `docs/etl/sprints/AI-OPS-364/evidence/senado_waf_block_profile_after_status404_packet50_refetch_20260301T092750Z.json`

## Conclusión
No hubo delta material y la lane queda cerrada por `no_new_lever` en esta iteración; el siguiente paso requiere captura/seed alterna para la cohorte `detalleiniciativa` sin snapshots públicos.
