# AI-OPS-330 - Retry Senado `status=403` con dedupe corregido + cierre de higiene local

## Objetivo
Continuar el cierre de `820/822` con una iteración reproducible sobre cola accionable Senado, evitando loops por dedupe excesivo y capturando delta real en descarga/procesado.

## Ejecución AI-OPS-330
1. Baseline de estado de iniciativas y perfil WAF linked-to-votes.
2. Validación de palanca manual/cookie:
- Captura manual fresca en 2 targets: ambos `Access Denied`.
- `report_senado_manual_capture_validity`: `status=ok`, `usable_captures_total=2`, `strict rc=0` (solo capturas históricas útiles).
- `report_senado_cookie_lever_status`: `status=degraded`, `strict rc=4`, `no_new_lever=true`, `cookie_file_stale`.
3. Export pool `status=403` (`329` filas) y corrección operativa de packetización:
- intento inicial con dedupe amplia dejó `fresh_rows_total=0` (sin retry efectivo).
- se corrige selección a `selection_method=retry_packet_only_dedup` (dedupe solo contra packets previos de retry).
4. Retry archivístico acotado sobre packet fresco corregido (`80` filas):
- `candidate_urls=80`, `urls_to_fetch=80`, `fetched_ok=2`.
- `archive_hits=2`, `archive_fetched_ok=2`, `text_documents_upserted=2`.
5. Post-proceso estructural:
- `backfill_initiative_doc_extractions --only-missing`: `seen=2`, `upserted=2`, `needs_review=0`.

## Delta medido (AI-OPS-329 -> AI-OPS-330)
- Descarga/doc status:
  - `downloaded_doc_links +2`.
  - `missing_doc_links -2`.
  - `missing_doc_links_actionable -2`.
  - `effective_downloaded_doc_links_pct +0.02`.
- Cola/WAF linked-to-votes:
  - `missing_urls -2`.
  - `blocked_403_urls -80`.
  - `blocked_500_urls 0` delta.
  - `unknown_status_urls 0` delta.

## Cierre de higiene local posterior
Se reejecuta verificación local de excerpt/cobertura tras AI-OPS-330:
- `report_initiative_doc_status` (senado): `downloaded_missing_excerpt=0`, `excerpt_coverage_pct=100.0`.
- `backfill_initiative_doc_excerpts`: no-op (`seen=0`, `updated=0`) sobre el estado actual.
- `report_initiative_doc_status` (congreso+senado):
  - `total_doc_links=9553`
  - `downloaded_doc_links=4413` (`46.19%`)
  - `missing_doc_links=5140`
  - `missing_doc_links_actionable=4956`
  - `doc_links_missing_fetch_status=217`
  - `linked_to_votes_with_downloaded_docs=746/751` (`99.33%`)
  - `effective_downloaded_doc_links_pct=47.10`

## Conclusión
- La iteración AI-OPS-330 aporta delta real en descarga (+2) y reduce cola accionable (`missing_urls -2`).
- El bloqueo externo persiste sin palanca nueva de captura (`cookie stale/no_new_lever`).
- Queda explicitada la deuda operativa de dedupe de packets para evitar no-deltas artificiales en futuras iteraciones.

## Evidencia
- `docs/etl/sprints/AI-OPS-330/evidence/initiative_doc_status_before_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/initiative_doc_status_after_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/initiative_doc_status_delta_ai_ops_330_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_waf_block_profile_before_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_waf_block_profile_after_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_waf_block_profile_delta_ai_ops_330_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_status403_fresh_packet_summary_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_retry_status403_fresh_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/initiative_doc_extractions_backfill_after_retry_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_status404_fresh_packet_summary_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_manual_capture_validity_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_manual_capture_validity_20260301T002838Z.rc`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_cookie_lever_status_20260301T002838Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_cookie_lever_status_20260301T002838Z.rc`
- `docs/etl/sprints/AI-OPS-330/evidence/initiative_doc_status_after_excerpts_senado_20260301T003915Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/initiative_doc_status_after_excerpts_overall_20260301T003915Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/senado_waf_block_profile_after_excerpts_20260301T003915Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/initiative_doc_excerpts_backfill_after_retry_20260301T003915Z.json`
- `docs/etl/sprints/AI-OPS-330/evidence/tracker_status_20260301T002838Z.log`
- `docs/etl/sprints/AI-OPS-330/evidence/tracker_status_after_tracker_update_20260301T004351Z.log`
