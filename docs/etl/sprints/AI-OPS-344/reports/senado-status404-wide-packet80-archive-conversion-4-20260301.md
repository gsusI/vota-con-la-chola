# AI-OPS-344 - lane status=404 (packet80) archive conversion

## Objetivo
Continuar `820/822/837/838` con un retry único acotado en `status=404` usando packet fresco + `archive fallback`, cerrando post-proceso de extracción/excerpts y actualizando KPIs.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Timestamp: `20260301T040942Z`
- Pool `status=404` linked-to-votes:
  - `pool_rows_total=680`
  - `fresh_rows_total=80`
  - `excluded_used_urls_total=208`
- Retry:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --doc-urls-file docs/etl/sprints/AI-OPS-344/exports/senado_status404_recent-window_packet_20260301T040942Z.csv --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404 --archive-timeout 6 --limit-initiatives 80 --max-docs-per-initiative 1 --timeout 12`

## Resultado del retry
- `candidate_urls=80`
- `urls_to_fetch=80`
- `fetched_ok=54`
- `archive_hits=54`
- `archive_fetched_ok=54`
- `archive_variant_hits=54`
- `archive_lookup_probe_requests=1202`
- `failures=26` (`archive fallback: no snapshot candidates`)

## Delta de KPIs
- `downloaded_doc_links: 4534 -> 4588` (`+54`)
- `missing_doc_links: 5019 -> 4965` (`-54`)
- `missing_doc_links_actionable: 4833 -> 4779` (`-54`)
- `effective_downloaded_doc_links_pct: 48.40 -> 48.98` (`+0.58`)
- `missing_urls (linked-to-votes): 1057 -> 1003` (`-54`)
- `blocked_403_urls: 160 -> 160` (estable)
- `unknown_status_urls: 217 -> 217` (estable)

## Estado post-slice
- `overall linked_to_votes_with_downloaded_docs`: `746/751` (sin cambio)
- `senado downloaded/total`: `3776/8741`
- Post-proceso sin regresión:
  - `backfill_initiative_doc_extractions --only-missing`: `seen=54`, `upserted=54`, `needs_review=0`
  - `backfill_initiative_doc_excerpts`: cobertura en descargados se mantiene `100%`

## Evidencia
- Packet summary:
  - `docs/etl/sprints/AI-OPS-344/evidence/senado_status404_recent-window_packet_summary_20260301T040942Z.json`
- Retry run:
  - `docs/etl/sprints/AI-OPS-344/evidence/senado_retry_status404_recent-window_packet80_20260301T040942Z.json`
  - `docs/etl/sprints/AI-OPS-344/evidence/senado_retry_status404_recent-window_packet80_20260301T040942Z.stderr.log`
- Estado/delta:
  - `docs/etl/sprints/AI-OPS-344/evidence/initiative_doc_status_before_20260301T040942Z.json`
  - `docs/etl/sprints/AI-OPS-344/evidence/initiative_doc_status_after_20260301T040942Z.json`
  - `docs/etl/sprints/AI-OPS-344/evidence/initiative_doc_status_delta_ai_ops_344_20260301T040942Z.json`
  - `docs/etl/sprints/AI-OPS-344/evidence/senado_waf_block_profile_before_20260301T040942Z.json`
  - `docs/etl/sprints/AI-OPS-344/evidence/senado_waf_block_profile_after_20260301T040942Z.json`
- Archive gap updated:
  - `docs/etl/sprints/AI-OPS-344/evidence/senado_archive_gap_urls_20260301T040942Z.json`
  - `docs/etl/sprints/AI-OPS-344/exports/senado_archive_gap_urls_20260301T040942Z.csv`
