# AI-OPS-349 - lane status=404 (packet80) archive conversion 8

## Objetivo
Continuar `820/822/837/838/840` con un retry único acotado en `status=404` usando packet fresco + `archive fallback`, cerrar post-proceso de extracción/excerpts y actualizar KPIs de cobertura.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Timestamp: `20260301T063939Z`
- Pool `status=404` linked-to-votes:
  - `pool_rows_total=503`
  - `fresh_rows_total=80`
  - `excluded_used_urls_total=352`
- Retry:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --doc-urls-file docs/etl/sprints/AI-OPS-349/exports/senado_status404_recent-window_packet_20260301T063939Z.csv --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404 --limit-initiatives 80 --max-docs-per-initiative 1 --timeout 12`

## Resultado del retry
- `candidate_urls=80`
- `urls_to_fetch=80`
- `fetched_ok=67`
- `archive_hits=67`
- `archive_fetched_ok=67`
- `archive_variant_hits=67`
- `archive_lookup_probe_requests=1145`
- `failures=13` (patrón dominante: `archive fallback: no snapshot candidates`)

## Delta de KPIs
- `downloaded_doc_links: 4707 -> 4774` (`+67`)
- `missing_doc_links: 4846 -> 4779` (`-67`)
- `missing_doc_links_actionable: 4656 -> 4589` (`-67`)
- `effective_downloaded_doc_links_pct: 50.27 -> 50.99` (`+0.72`)
- `missing_urls (linked-to-votes): 880 -> 813` (`-67`)
- `missing_initiatives: 585 -> 576` (`-9`)
- `blocked_403_urls: 160 -> 160` (estable)
- `unknown_status_urls: 217 -> 217` (estable)
- `zero_doc_initiatives: 5 -> 5` (sin cierre)

## Estado post-slice
- `overall linked_to_votes_with_downloaded_docs`: `746/751` (sin cambio)
- `senado downloaded/total`: `3962/8741`
- Post-proceso sin regresión:
  - `backfill_initiative_doc_extractions --only-missing`: `seen=67`, `upserted=67`, `needs_review=0`
  - `backfill_initiative_doc_excerpts`: `seen=1`, `updated=1`
  - Cobertura de excerpt/extracción en descargados se mantiene `100%`
- Gap archive consolidado (histórico `AI-OPS-*`):
  - `archive_no_snapshot_failures_total=411`
  - `unique_urls_total=306`

## Evidencia
- Packet summary:
  - `docs/etl/sprints/AI-OPS-349/evidence/senado_status404_recent-window_packet_summary_20260301T063939Z.json`
- Retry run:
  - `docs/etl/sprints/AI-OPS-349/evidence/senado_retry_status404_recent-window_packet80_20260301T063939Z.json`
  - `docs/etl/sprints/AI-OPS-349/evidence/senado_retry_status404_recent-window_packet80_20260301T063939Z.stderr.log`
- Estado/delta:
  - `docs/etl/sprints/AI-OPS-349/evidence/initiative_doc_status_before_20260301T063939Z.json`
  - `docs/etl/sprints/AI-OPS-349/evidence/initiative_doc_status_after_20260301T063939Z.json`
  - `docs/etl/sprints/AI-OPS-349/evidence/initiative_doc_status_delta_ai_ops_349_20260301T063939Z.json`
  - `docs/etl/sprints/AI-OPS-349/evidence/senado_waf_block_profile_before_20260301T063939Z.json`
  - `docs/etl/sprints/AI-OPS-349/evidence/senado_waf_block_profile_after_20260301T063939Z.json`
  - `docs/etl/sprints/AI-OPS-349/evidence/senado_waf_block_profile_delta_ai_ops_349_20260301T063939Z.json`
- Post-proceso:
  - `docs/etl/sprints/AI-OPS-349/evidence/initiative_doc_extractions_backfill_after_retry_20260301T063939Z.json`
  - `docs/etl/sprints/AI-OPS-349/evidence/initiative_doc_excerpts_backfill_after_retry_20260301T063939Z.json`
- Archive gap updated:
  - `docs/etl/sprints/AI-OPS-349/evidence/senado_archive_gap_urls_20260301T063939Z.json`
  - `docs/etl/sprints/AI-OPS-349/exports/senado_archive_gap_urls_20260301T063939Z.csv`
