# AI-OPS-331 - Retry Senado `status=403` con dedupe por packet-only y verificación de agotamiento `status=404`

## Objetivo
Continuar el cierre de `820/822` con una iteración reproducible de descarga/procesado en Senado, usando dedupe canónico basado solo en packets de retry previos y sin repetir loops de cohortes agotadas.

## Ejecución
1. Baseline de estado iniciativas + perfil WAF linked-to-votes.
2. Verificación de palanca manual/cookie:
- `report_senado_manual_capture_validity`: `status=ok`, `strict rc=0`, `captures_total=1`, `usable_captures_total=1`.
- `report_senado_cookie_lever_status`: `status=degraded`, `strict rc=4`, `strict_fail_reasons=[cookie_file_stale]`.
3. Export de pools accionables:
- `status=403`: `pool_rows_total=249`.
- `status=404`: `pool_rows_total=714`.
4. Packetización `retry_packet_only_dedup`:
- `status=403`: `excluded_used_urls_total=89`, `fresh_rows_total=80`.
- `status=404`: `excluded_used_urls_total=714`, `fresh_rows_total=0` (cohorte agotada bajo dedupe canónico).
5. Único retry de red del sprint (`status=403`, packet 80 filas):
- `candidate_urls=80`, `urls_to_fetch=80`, `fetched_ok=1`.
- `archive_hits=1`, `archive_fetched_ok=1`, `text_documents_upserted=1`.
6. Post-proceso local:
- `backfill_initiative_doc_extractions --only-missing`: `seen=1`, `upserted=1`, `needs_review=0`.
- `backfill_initiative_doc_excerpts`: `seen=1`, `updated=1`.

## Delta medido (AI-OPS-330 -> AI-OPS-331)
- `downloaded_doc_links +1` (`4413 -> 4414`)
- `missing_doc_links -1` (`5140 -> 5139`)
- `missing_doc_links_actionable -1` (`4956 -> 4955`)
- `effective_downloaded_doc_links_pct +0.01` (`47.10 -> 47.11`)
- `missing_urls -1` (`1180 -> 1179`)
- `blocked_403_urls -80` (`249 -> 169`)
- `blocked_500_urls 0` delta
- `unknown_status_urls 0` delta (`217`)

## Estado posterior
- Overall (`congreso+senado`):
  - `total_doc_links=9553`
  - `downloaded_doc_links=4414` (`46.21%`)
  - `missing_doc_links=5139`
  - `missing_doc_links_actionable=4955`
  - `doc_links_missing_fetch_status=217`
  - `effective_downloaded_doc_links_pct=47.11`
  - `excerpt_coverage_pct=100.0`, `extraction_coverage_pct=100.0`
- WAF linked-to-votes (Senado):
  - `missing_urls=1179`
  - `blocked_403_urls=169`
  - `blocked_500_urls=0`
  - `unknown_status_urls=217`
  - `missing_initiatives=627`, `zero_doc_initiatives=5`

## Conclusión
- Se mantiene progreso neto en scraping/procesado (`+1`) y reducción de cola accionable (`-1`) con una iteración acotada y reproducible.
- La lane `status=404` queda efectivamente agotada bajo dedupe packet-only (`fresh_rows_total=0`), por lo que la siguiente iteración de red debe priorizar `status=403` mientras persista `no_new_lever` en cookie.
- Persiste deuda de producto en formalizar este contrato de dedupe dentro del toolchain (hoy está ejecutado operacionalmente con evidencia del sprint).

## Evidencia
- `docs/etl/sprints/AI-OPS-331/evidence/initiative_doc_status_before_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/initiative_doc_status_after_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/initiative_doc_status_delta_ai_ops_331_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_waf_block_profile_before_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_waf_block_profile_after_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_waf_block_profile_delta_ai_ops_331_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_status403_fresh_packet_summary_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_status404_fresh_packet_summary_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_retry_status403_fresh_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/initiative_doc_extractions_backfill_after_retry_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/initiative_doc_excerpts_backfill_after_retry_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_manual_capture_validity_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_manual_capture_validity_20260301T004653Z.rc`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_cookie_lever_status_20260301T004653Z.json`
- `docs/etl/sprints/AI-OPS-331/evidence/senado_cookie_lever_status_20260301T004653Z.rc`
- `docs/etl/sprints/AI-OPS-331/evidence/tracker_status_after_tracker_update_20260301T004653Z.log`
