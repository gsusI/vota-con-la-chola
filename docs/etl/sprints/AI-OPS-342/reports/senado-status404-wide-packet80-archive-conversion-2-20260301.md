# AI-OPS-342 - lane status=404 (packet80) archive conversion

## Objetivo
Continuar `820/822/837/838` con un retry único acotado en `status=404` usando packet fresco + `archive fallback`, cerrando post-proceso de extracción/excerpts y actualizando KPIs.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Timestamp: `20260301T030721Z`
- Pool `status=404` linked-to-votes:
  - `pool_rows_total=772`
  - `fresh_rows_total=80`
  - `excluded_used_urls_total=140`
- Retry:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --doc-urls-file docs/etl/sprints/AI-OPS-342/exports/senado_status404_recent-window_packet_20260301T030721Z.csv --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404 --archive-timeout 6 --limit-initiatives 80 --max-docs-per-initiative 1 --timeout 12`

## Resultado del retry
- `candidate_urls=80`
- `urls_to_fetch=80`
- `fetched_ok=32`
- `archive_hits=32`
- `archive_fetched_ok=32`
- `archive_variant_hits=32`
- `archive_lookup_probe_requests=1043`
- `failures=30` (`archive fallback: no snapshot candidates`)

## Delta de KPIs
- `downloaded_doc_links: 4443 -> 4475` (`+32`)
- `missing_doc_links: 5110 -> 5078` (`-32`)
- `missing_doc_links_actionable: 4925 -> 4892` (`-33`)
- `effective_downloaded_doc_links_pct: 47.43 -> 47.77` (`+0.34`)
- `missing_urls (linked-to-votes): 1149 -> 1116` (`-33`)
- `blocked_403_urls: 160 -> 160` (estable)
- `unknown_status_urls: 217 -> 217` (estable)

## Estado post-slice
- `overall linked_to_votes_with_downloaded_docs`: `746/751` (sin cambio)
- `senado downloaded/total`: `3663/8741`
- Post-proceso sin regresión:
  - `backfill_initiative_doc_extractions --only-missing`: `seen=32`, `upserted=32`, `needs_review=0`
  - `backfill_initiative_doc_excerpts`: cobertura en descargados se mantiene `100%`

## Evidencia
- Packet summary:
  - `docs/etl/sprints/AI-OPS-342/evidence/senado_status404_recent-window_packet_summary_20260301T030721Z.json`
- Retry run:
  - `docs/etl/sprints/AI-OPS-342/evidence/senado_retry_status404_recent-window_packet80_20260301T030721Z.json`
  - `docs/etl/sprints/AI-OPS-342/evidence/senado_retry_status404_recent-window_packet80_20260301T030721Z.stderr.log`
- Estado/delta:
  - `docs/etl/sprints/AI-OPS-342/evidence/initiative_doc_status_before_20260301T030721Z.json`
  - `docs/etl/sprints/AI-OPS-342/evidence/initiative_doc_status_after_20260301T030721Z.json`
  - `docs/etl/sprints/AI-OPS-342/evidence/initiative_doc_status_delta_ai_ops_342_20260301T030721Z.json`
  - `docs/etl/sprints/AI-OPS-342/evidence/senado_waf_block_profile_before_20260301T030721Z.json`
  - `docs/etl/sprints/AI-OPS-342/evidence/senado_waf_block_profile_after_20260301T030721Z.json`
- Archive gap updated:
  - `docs/etl/sprints/AI-OPS-342/evidence/senado_archive_gap_urls_20260301T030721Z.json`
  - `docs/etl/sprints/AI-OPS-342/exports/senado_archive_gap_urls_20260301T030721Z.csv`
