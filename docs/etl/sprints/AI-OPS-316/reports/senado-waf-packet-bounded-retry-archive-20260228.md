# AI-OPS-316 — Retry acotado por packet WAF (Senado) con fallback archivístico

## Objetivo

Ejecutar un único retry de red acotado por sprint sobre una cohorte fija de URLs Senado (`only_linked_to_votes`) para reducir cola accionable de `820/822` sin abrir nuevas superficies.

## Preparación

DB: `etl/data/staging/politicos-es.db`

- Baseline de cobertura: `report_initiative_doc_status`.
- Baseline de cola/WAF: `report_senado_waf_block_profile` + `export_missing_initiative_doc_urls`.
- Packet fijo generado con `export_senado_waf_cohort_packets`:
  - `packet_rows_total=80`
  - `selected_cohorts_total=5`
  - `packet_unique_initiatives_total=72`

Gate manual capture previo:
- `status=degraded`, `usable_captures_total=0`, strict `rc=4`.

## Ejecución

Retry único sobre packet fijo (`--doc-urls-file`) con:
- `--retry-http-statuses 403,404,500`
- `--archive-fallback --archive-fallback-http-statuses 403,404,500`
- `--skip-link-backfill`

Resultado del retry:
- `candidate_urls=79`
- `urls_to_fetch=79`
- `fetched_ok=7`
- `archive_fetched_ok=7`
- `archive_hits=7`
- `selected_scope_no_limit=true`

Post-proceso:
- `backfill_initiative_doc_extractions --only-missing`:
  - `seen=7`, `upserted=7`, `needs_review=0`.

## Delta medido

Cobertura iniciativas (`before -> after`):
- `downloaded_doc_links: 4334 -> 4341` (`+7`)
- `missing_doc_links: 5219 -> 5212` (`-7`)
- `missing_doc_links_actionable: 5035 -> 5028` (`-7`)
- `effective_downloaded_doc_links_pct: 46.26 -> 46.33` (`+0.07pp`)

Senado (`before -> after`):
- `downloaded_doc_links: 3522 -> 3529` (`+7`)
- `missing_doc_links: 5219 -> 5212` (`-7`)
- `missing_doc_links_actionable: 5035 -> 5028` (`-7`)

Cola/WAF `only_linked_to_votes` (`before -> after`):
- `missing_urls: 1259 -> 1252` (`-7`)
- `blocked_403_urls: 705 -> 666` (`-39`)
- `blocked_500_urls: 134 -> 101` (`-33`)
- `unknown_status_urls: 377 -> 377` (`=0`)
- `zero_doc_initiatives: 6 -> 6` (`=0`)
- CSV cola accionable: `1260 -> 1253` líneas (incl. cabecera), `-7`.

## Estado

- `visible_progress`: YES (reducción material de cola y cobertura +7 en DB real).
- Bloqueo externo persiste (`manual capture degraded`, sin cookie utilizable).

## Evidencia

- `docs/etl/sprints/AI-OPS-316/evidence/senado_waf_packet_summary_20260228T222329Z.json`
- `docs/etl/sprints/AI-OPS-316/exports/senado_waf_packet_20260228T222329Z.csv`
- `docs/etl/sprints/AI-OPS-316/evidence/senado_retry_packet_statuses_403_404_500_20260228T222329Z.json`
- `docs/etl/sprints/AI-OPS-316/evidence/initiative_doc_extractions_backfill_after_retry_20260228T222329Z.json`
- `docs/etl/sprints/AI-OPS-316/evidence/initiative_doc_status_delta_ai_ops_316_20260228T222329Z.json`
- `docs/etl/sprints/AI-OPS-316/evidence/senado_waf_block_profile_delta_ai_ops_316_20260228T222329Z.json`
- `docs/etl/sprints/AI-OPS-316/evidence/senado_tail_actionable_delta_ai_ops_316_20260228T222329Z.json`
- `docs/etl/sprints/AI-OPS-316/evidence/senado_manual_capture_validity_20260228T222329Z.json`
- `docs/etl/sprints/AI-OPS-316/evidence/senado_manual_capture_validity_20260228T222329Z.rc`
- `docs/etl/sprints/AI-OPS-316/evidence/unittest_senado_waf_packet_and_profile_lane_20260228T222329Z.txt`
- `docs/etl/sprints/AI-OPS-316/evidence/tracker_status_20260228T222329Z.log`
