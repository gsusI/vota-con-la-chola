# AI-OPS-347 - zero_doc linked-to-votes (retry acotado + estructuración)

## Objetivo
Avanzar la fila `840` (iniciativas Senado `linked_to_votes` sin ningún documento descargado) con un retry reproducible sobre la cola completa `zero_doc`, manteniendo post-proceso y dejando una cola priorizada operativa para cierre.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Timestamp: `20260301T055144Z`
- Pool `zero_doc` (`only_actionable_missing + only_linked_to_votes + only_initiatives_without_any_doc`):
  - `pool_rows_total=17`
  - `excluded_redundant_senado_global=189`
  - `excluded_initiatives_with_downloaded_docs=922`
- Dedupe contra packets históricos:
  - `fresh_rows_total=1` (de `17`)
  - `excluded_used_urls_total=16`
- Retry ejecutado sobre pool completo (`17` URLs):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --doc-urls-file docs/etl/sprints/AI-OPS-347/exports/senado_zero_doc_actionable_pool_20260301T055144Z.csv --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404 --archive-timeout 6 --limit-initiatives 40 --max-docs-per-initiative 2 --timeout 15`

## Resultado del retry
- `candidate_urls=17`
- `urls_to_fetch=17`
- `fetched_ok=0`
- `archive_hits=0`
- `archive_fetched_ok=0`
- `archive_variant_hits=0`
- `archive_lookup_probe_requests=215`
- `failures=17` (patrón dominante: `archive fallback: no snapshot candidates`)

## Delta de KPIs
- `downloaded_doc_links: 4648 -> 4648` (`+0`)
- `missing_doc_links: 4905 -> 4905` (`0`)
- `missing_doc_links_actionable: 4715 -> 4715` (`0`)
- `effective_downloaded_doc_links_pct: 49.64 -> 49.64` (`0.00`)
- `missing_urls (linked-to-votes): 939 -> 939` (`0`)
- `blocked_403_urls: 160 -> 160` (estable)
- `unknown_status_urls: 217 -> 217` (estable)
- `zero_doc_initiatives: 5 -> 5` (sin cierre)

## Estado post-slice
- `overall linked_to_votes_with_downloaded_docs`: `746/751` (sin cambio)
- Post-proceso sin regresión:
  - `backfill_initiative_doc_extractions --only-missing`: `seen=0`, `upserted=0`, `needs_review=0`
  - `backfill_initiative_doc_excerpts`: `seen=0`, `updated=0`
- Se estructura cola prioritaria exportable para siguiente sprint:
  - `senado_zero_doc_priority_20260301T055144Z.csv` (`5` iniciativas top)
  - foco: cohortes `leg14 tipo622/626` con `404` persistente + falta de snapshots.

## Evidencia
- Retry y packetización:
  - `docs/etl/sprints/AI-OPS-347/evidence/senado_zero_doc_actionable_pool_20260301T055144Z.stdout.log`
  - `docs/etl/sprints/AI-OPS-347/evidence/senado_zero_doc_recent-window_packet_summary_20260301T055144Z.json`
  - `docs/etl/sprints/AI-OPS-347/evidence/senado_retry_zero_doc_actionable_20260301T055144Z.json`
  - `docs/etl/sprints/AI-OPS-347/evidence/senado_retry_zero_doc_actionable_20260301T055144Z.stderr.log`
- Estado/delta:
  - `docs/etl/sprints/AI-OPS-347/evidence/initiative_doc_status_before_20260301T055144Z.json`
  - `docs/etl/sprints/AI-OPS-347/evidence/initiative_doc_status_after_20260301T055144Z.json`
  - `docs/etl/sprints/AI-OPS-347/evidence/initiative_doc_status_delta_ai_ops_347_20260301T055144Z.json`
  - `docs/etl/sprints/AI-OPS-347/evidence/senado_waf_block_profile_before_20260301T055144Z.json`
  - `docs/etl/sprints/AI-OPS-347/evidence/senado_waf_block_profile_after_20260301T055144Z.json`
- Gap archive y cola prioritaria:
  - `docs/etl/sprints/AI-OPS-347/evidence/senado_archive_gap_urls_20260301T055144Z.json`
  - `docs/etl/sprints/AI-OPS-347/exports/senado_archive_gap_urls_20260301T055144Z.csv`
  - `docs/etl/sprints/AI-OPS-347/exports/senado_zero_doc_priority_20260301T055144Z.csv`
