# AI-OPS-348 - lane status=404 (packet80) archive conversion 7

## Objetivo
Continuar `820/822/837/838` con un retry único acotado en `status=404` usando packet fresco + `archive fallback`, cerrar post-proceso de extracción/excerpts y actualizar KPIs de cobertura.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Timestamp: `20260301T060032Z`
- Pool `status=404` linked-to-votes:
  - `pool_rows_total=562`
  - `fresh_rows_total=80`
  - `excluded_used_urls_total=331`
- Retry:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --doc-urls-file docs/etl/sprints/AI-OPS-348/exports/senado_status404_recent-window_packet_20260301T060032Z.csv --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404 --archive-timeout 6 --limit-initiatives 80 --max-docs-per-initiative 1 --timeout 12`

## Resultado del retry
- `candidate_urls=80`
- `urls_to_fetch=80`
- `fetched_ok=59`
- `archive_hits=59`
- `archive_fetched_ok=59`
- `archive_variant_hits=59`
- `archive_lookup_probe_requests=1187`
- `failures=21` (patrón dominante: `archive fallback: no snapshot candidates`)

## Delta de KPIs
- `downloaded_doc_links: 4648 -> 4707` (`+59`)
- `missing_doc_links: 4905 -> 4846` (`-59`)
- `missing_doc_links_actionable: 4715 -> 4656` (`-59`)
- `effective_downloaded_doc_links_pct: 49.64 -> 50.27` (`+0.63`)
- `missing_urls (linked-to-votes): 939 -> 880` (`-59`)
- `missing_initiatives: 600 -> 585` (`-15`)
- `blocked_403_urls: 160 -> 160` (estable)
- `unknown_status_urls: 217 -> 217` (estable)
- `zero_doc_initiatives: 5 -> 5` (sin cierre)

## Estado post-slice
- `overall linked_to_votes_with_downloaded_docs`: `746/751` (sin cambio)
- `senado downloaded/total`: `3895/8741`
- Post-proceso sin regresión:
  - `backfill_initiative_doc_extractions --only-missing`: `seen=59`, `upserted=59`, `needs_review=0`
  - `backfill_initiative_doc_excerpts`: cobertura en descargados se mantiene `100%`
- Gap archive consolidado (histórico `AI-OPS-*`):
  - `archive_no_snapshot_failures_total=398`
  - `unique_urls_total=295`

## Evidencia
- Packet summary:
  - `docs/etl/sprints/AI-OPS-348/evidence/senado_status404_recent-window_packet_summary_20260301T060032Z.json`
- Retry run:
  - `docs/etl/sprints/AI-OPS-348/evidence/senado_retry_status404_recent-window_packet80_20260301T060032Z.json`
  - `docs/etl/sprints/AI-OPS-348/evidence/senado_retry_status404_recent-window_packet80_20260301T060032Z.stderr.log`
- Estado/delta:
  - `docs/etl/sprints/AI-OPS-348/evidence/initiative_doc_status_before_20260301T060032Z.json`
  - `docs/etl/sprints/AI-OPS-348/evidence/initiative_doc_status_after_20260301T060032Z.json`
  - `docs/etl/sprints/AI-OPS-348/evidence/initiative_doc_status_delta_ai_ops_348_20260301T060032Z.json`
  - `docs/etl/sprints/AI-OPS-348/evidence/senado_waf_block_profile_before_20260301T060032Z.json`
  - `docs/etl/sprints/AI-OPS-348/evidence/senado_waf_block_profile_after_20260301T060032Z.json`
  - `docs/etl/sprints/AI-OPS-348/evidence/senado_waf_block_profile_delta_ai_ops_348_20260301T060032Z.json`
- Archive gap updated:
  - `docs/etl/sprints/AI-OPS-348/evidence/senado_archive_gap_urls_20260301T060032Z.json`
  - `docs/etl/sprints/AI-OPS-348/exports/senado_archive_gap_urls_20260301T060032Z.csv`
- Estado tracker:
  - `docs/etl/sprints/AI-OPS-348/evidence/tracker_status_20260301T060032Z.log`
  - `docs/etl/sprints/AI-OPS-348/evidence/e2e_tracker_status_20260301T060032Z.log`
