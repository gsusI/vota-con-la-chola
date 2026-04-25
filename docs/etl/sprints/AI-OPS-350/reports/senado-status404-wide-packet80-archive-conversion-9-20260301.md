# AI-OPS-350 - lane status=404 (packet80) archive conversion 9

## Objetivo
Continuar `820/822/837/838/840` con un retry único acotado en `status=404` usando packet fresco + `archive fallback`, cerrar post-proceso de extracción/excerpts y actualizar KPIs de cobertura.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Timestamp: `20260301T071518Z`
- Pool `status=404` linked-to-votes:
  - `pool_rows_total=436`
  - `fresh_rows_total=69`
  - `excluded_used_urls_total=367`
- Retry:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --doc-urls-file docs/etl/sprints/AI-OPS-350/exports/senado_status404_recent-window_packet_20260301T071518Z.csv --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404 --limit-initiatives 80 --max-docs-per-initiative 1 --timeout 12`

## Resultado del retry
- `candidate_urls=69`
- `urls_to_fetch=69`
- `fetched_ok=28`
- `archive_hits=28`
- `archive_fetched_ok=28`
- `archive_variant_hits=28`
- `archive_lookup_probe_requests=897`
- `failures=30` (patrón dominante: `archive fallback: no snapshot candidates`)

## Delta de KPIs
- `downloaded_doc_links: 4774 -> 4802` (`+28`)
- `missing_doc_links: 4779 -> 4751` (`-28`)
- `missing_doc_links_actionable: 4589 -> 4561` (`-28`)
- `effective_downloaded_doc_links_pct: 50.99 -> 51.29` (`+0.30`)
- `missing_urls (linked-to-votes): 813 -> 785` (`-28`)
- `missing_initiatives: 576 -> 548` (`-28`)
- `blocked_403_urls: 160 -> 160` (estable)
- `unknown_status_urls: 217 -> 217` (estable)
- `zero_doc_initiatives: 5 -> 5` (sin cierre)

## Estado post-slice
- `overall linked_to_votes_with_downloaded_docs`: `746/751` (sin cambio)
- `senado downloaded/total`: `3990/8741`
- Post-proceso sin regresión:
  - `backfill_initiative_doc_extractions --only-missing`: `seen=28`, `upserted=28`, `needs_review=0`
  - `backfill_initiative_doc_excerpts`: `seen=0`, `updated=0`
  - Cobertura de excerpt/extracción en descargados se mantiene `100%`
- Gap archive consolidado (histórico `AI-OPS-*`):
  - `archive_no_snapshot_failures_total=441`
  - `unique_urls_total=316`

## Evidencia
- Packet summary:
  - `docs/etl/sprints/AI-OPS-350/evidence/senado_status404_recent-window_packet_summary_20260301T071518Z.json`
- Retry run:
  - `docs/etl/sprints/AI-OPS-350/evidence/senado_retry_status404_recent-window_packet80_20260301T071518Z.json`
  - `docs/etl/sprints/AI-OPS-350/evidence/senado_retry_status404_recent-window_packet80_20260301T071518Z.stderr.log`
- Estado/delta:
  - `docs/etl/sprints/AI-OPS-350/evidence/initiative_doc_status_before_20260301T071518Z.json`
  - `docs/etl/sprints/AI-OPS-350/evidence/initiative_doc_status_after_20260301T071518Z.json`
  - `docs/etl/sprints/AI-OPS-350/evidence/initiative_doc_status_delta_ai_ops_350_20260301T071518Z.json`
  - `docs/etl/sprints/AI-OPS-350/evidence/senado_waf_block_profile_before_20260301T071518Z.json`
  - `docs/etl/sprints/AI-OPS-350/evidence/senado_waf_block_profile_after_20260301T071518Z.json`
  - `docs/etl/sprints/AI-OPS-350/evidence/senado_waf_block_profile_delta_ai_ops_350_20260301T071518Z.json`
- Post-proceso:
  - `docs/etl/sprints/AI-OPS-350/evidence/initiative_doc_extractions_backfill_after_retry_20260301T071518Z.json`
  - `docs/etl/sprints/AI-OPS-350/evidence/initiative_doc_excerpts_backfill_after_retry_20260301T071518Z.json`
- Archive gap updated:
  - `docs/etl/sprints/AI-OPS-350/evidence/senado_archive_gap_urls_20260301T071518Z.json`
  - `docs/etl/sprints/AI-OPS-350/exports/senado_archive_gap_urls_20260301T071518Z.csv`
