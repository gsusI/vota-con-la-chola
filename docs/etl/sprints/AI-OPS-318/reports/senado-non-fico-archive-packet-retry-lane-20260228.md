# AI-OPS-318 — Retry acotado por familia URL (Senado) excluyendo `ficopendataservlet`

## Objetivo

Avanzar las filas `820/822` con una palanca nueva bajo control del repo: priorizar cola accionable no-`ficopendataservlet` (familias `enmiendas/index.html` y `detalleiniciativa`) para maximizar recuperación archivística y reducir cierre en falso por URLs de bajo rendimiento.

## Preparación

DB: `etl/data/staging/politicos-es.db`

Baseline pre-run (`only_linked_to_votes`):

- `missing_urls=1252`
- `blocked_403_urls=666`
- `blocked_500_urls=101`
- `unknown_status_urls=297`
- cola accionable CSV: `1253` líneas (incl. cabecera).

Gate manual capture previo:

- `status=degraded`, `usable_captures_total=0`, strict `rc=4`.

Packet dirigido (`max_total_rows=80`, `max_urls_per_initiative=1`, excluyendo `ficopendataservlet`):

- `packet_rows_total=80`
- `packet_unique_initiatives_total=80`
- `status_buckets`: `500=65`, `404=15`
- `family_buckets`: `enmiendas_index_html=77`, `detalleiniciativa_html=3`.

## Ejecución

Retry único sobre packet fijo (`--doc-urls-file`) con:

- `--retry-http-statuses 404,500`
- `--archive-fallback --archive-fallback-http-statuses 404,500`
- `--skip-link-backfill`

Resultado del retry:

- `candidate_urls=80`
- `urls_to_fetch=80`
- `fetched_ok=6`
- `archive_lookup_attempted=80`
- `archive_hits=6`
- `archive_fetched_ok=6`
- `text_documents_upserted=6`
- `selected_scope_no_limit=true`

Post-proceso:

- `backfill_initiative_doc_extractions --only-missing`:
  - `seen=6`, `upserted=6`, `needs_review=0`.

## Delta medido

Cobertura iniciativas (`before -> after`):

- `downloaded_doc_links: 4341 -> 4347` (`+6`)
- `missing_doc_links: 5212 -> 5206` (`-6`)
- `missing_doc_links_actionable: 5028 -> 5022` (`-6`)
- `effective_downloaded_doc_links_pct: 46.33 -> 46.40` (`+0.07pp`)

Senado (`before -> after`):

- `downloaded_doc_links: 3529 -> 3535` (`+6`)
- `missing_doc_links: 5212 -> 5206` (`-6`)
- `missing_doc_links_actionable: 5028 -> 5022` (`-6`)

Cola/WAF `only_linked_to_votes` (`before -> after`):

- `missing_urls: 1252 -> 1246` (`-6`)
- `blocked_403_urls: 666 -> 666` (`=0`)
- `blocked_500_urls: 101 -> 36` (`-65`)
- `unknown_status_urls: 297 -> 297` (`=0`)
- `zero_doc_initiatives: 6 -> 6` (`=0`)
- CSV cola accionable: `1253 -> 1247` líneas (incl. cabecera), `-6`.

## Estado

- `visible_progress`: YES (reducción material de cola accionable y cobertura `+6` en DB real).
- Bloqueo externo persiste (captura manual `degraded`, sin cookie utilizable).

## Evidencia

- `docs/etl/sprints/AI-OPS-318/evidence/senado_non_fico_packet_summary_20260228T224436Z.json`
- `docs/etl/sprints/AI-OPS-318/exports/senado_non_fico_packet_20260228T224436Z.csv`
- `docs/etl/sprints/AI-OPS-318/evidence/senado_retry_non_fico_statuses_404_500_20260228T224436Z.json`
- `docs/etl/sprints/AI-OPS-318/evidence/initiative_doc_extractions_backfill_after_retry_20260228T224436Z.json`
- `docs/etl/sprints/AI-OPS-318/evidence/initiative_doc_status_delta_ai_ops_318_20260228T224436Z.json`
- `docs/etl/sprints/AI-OPS-318/evidence/senado_waf_block_profile_delta_ai_ops_318_20260228T224436Z.json`
- `docs/etl/sprints/AI-OPS-318/evidence/senado_tail_actionable_delta_ai_ops_318_20260228T224436Z.json`
- `docs/etl/sprints/AI-OPS-318/evidence/senado_manual_capture_validity_20260228T224436Z.json`
- `docs/etl/sprints/AI-OPS-318/evidence/senado_manual_capture_validity_20260228T224436Z.rc`
- `docs/etl/sprints/AI-OPS-318/evidence/tracker_status_20260228T224436Z.log`
