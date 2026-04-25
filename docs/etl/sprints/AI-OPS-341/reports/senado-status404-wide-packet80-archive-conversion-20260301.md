# AI-OPS-341 - lane status=404 (packet80) archive conversion

## Objetivo
Avanzar `820/822/837/838` con un retry único acotado en `status=404` usando packet fresco + `archive fallback` y cerrar el loop de post-proceso/estado.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Timestamp: `20260301T023238Z`
- Pool `status=404` linked-to-votes:
  - `pool_rows_total=792`
  - `fresh_rows_total=80`
  - `excluded_used_urls_total=16`
- Retry:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --doc-urls-file docs/etl/sprints/AI-OPS-341/exports/senado_status404_recent-window_packet_20260301T023238Z.csv --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404 --archive-timeout 6 --limit-initiatives 80 --max-docs-per-initiative 1 --timeout 12`

## Resultado del retry
- `candidate_urls=80`
- `urls_to_fetch=80`
- `fetched_ok=19`
- `archive_hits=19`
- `archive_fetched_ok=19`
- `archive_variant_hits=19`
- `failures=30`

## Delta de KPIs
- `downloaded_doc_links: 4424 -> 4443` (`+19`)
- `missing_doc_links: 5129 -> 5110` (`-19`)
- `missing_doc_links_actionable: 4945 -> 4925` (`-20`)
- `effective_downloaded_doc_links_pct: 47.22 -> 47.43`
- `missing_urls (linked-to-votes): 1169 -> 1149` (`-20`)
- `blocked_403_urls: 160 -> 160` (estable)
- `unknown_status_urls: 217 -> 217` (estable)

## Estado post-slice
- `overall linked_to_votes_with_downloaded_docs`: `746/751` (sin cambio)
- `senado downloaded/total`: `3631/8741`
- Post-proceso sin regresión:
  - `backfill_initiative_doc_extractions` ejecutado
  - `backfill_initiative_doc_excerpts` ejecutado

## Evidencia
- Packet summary:
  - `docs/etl/sprints/AI-OPS-341/evidence/senado_status404_recent-window_packet_summary_20260301T023238Z.json`
- Retry run:
  - `docs/etl/sprints/AI-OPS-341/evidence/senado_retry_status404_recent-window_packet80_20260301T023238Z.json`
  - `docs/etl/sprints/AI-OPS-341/evidence/senado_retry_status404_recent-window_packet80_20260301T023238Z.stderr.log`
- Estado/delta:
  - `docs/etl/sprints/AI-OPS-341/evidence/initiative_doc_status_before_20260301T023238Z.json`
  - `docs/etl/sprints/AI-OPS-341/evidence/initiative_doc_status_after_20260301T023238Z.json`
  - `docs/etl/sprints/AI-OPS-341/evidence/initiative_doc_status_delta_ai_ops_341_20260301T023238Z.json`
  - `docs/etl/sprints/AI-OPS-341/evidence/senado_waf_block_profile_before_20260301T023238Z.json`
  - `docs/etl/sprints/AI-OPS-341/evidence/senado_waf_block_profile_after_20260301T023238Z.json`
- Archive gap updated:
  - `docs/etl/sprints/AI-OPS-341/evidence/senado_archive_gap_urls_20260301T023238Z.json`
  - `docs/etl/sprints/AI-OPS-341/exports/senado_archive_gap_urls_20260301T023238Z.csv`
- Tracker parser:
  - `docs/etl/sprints/AI-OPS-341/evidence/tracker_status_20260301T023238Z.log`
