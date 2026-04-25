# AI-OPS-351 - packet exhaustion check + status=500 lane decision

## Objetivo
Ejecutar el DoD del nuevo lane `status=500` y validar capacidad fresca de los lanes `status=404` y `zero_doc` bajo dedupe canónico, con decisión explícita `keep_or_drop`.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Timestamp: `20260301T074257Z`
- Lanes evaluadas:
  - `status=500` linked-to-votes (max `40`)
  - `status=404` linked-to-votes (max `40`)
  - `zero_doc` linked-to-votes (max `20`)

## Resultado
- `status=500`:
  - `pool_rows_total=0`
  - `fresh_rows_total=0`
  - `strict_fail_reasons=[no_pool_rows,fresh_rows_below_min]`
- `status=404`:
  - `pool_rows_total=408`
  - `fresh_rows_total=0`
  - `strict_fail_reasons=[fresh_rows_below_min,packet_exhausted_by_canonical_dedupe]`
- `zero_doc`:
  - `pool_rows_total=17`
  - `fresh_rows_total=0`
  - `strict_fail_reasons=[fresh_rows_below_min,packet_exhausted_by_canonical_dedupe]`

## Decisión de lane
- `status500_linked_to_votes`: `drop_for_now_no_pool_rows`
- `status404_linked_to_votes`: `blocked_packet_exhausted_by_canonical_dedupe`
- `zero_doc_linked_to_votes`: `blocked_packet_exhausted_by_canonical_dedupe`

## Delta de KPIs
- Sin cambios en cobertura durante este slice:
  - `downloaded_doc_links: 4802 -> 4802`
  - `missing_doc_links_actionable: 4561 -> 4561`
  - `missing_urls: 785 -> 785`
  - `zero_doc_initiatives: 5 -> 5`

## Evidencia
- Paquete/decisión `status=500`:
  - `docs/etl/sprints/AI-OPS-351/evidence/senado_status500_actionable_pool_20260301T074257Z.stdout.log`
  - `docs/etl/sprints/AI-OPS-351/evidence/senado_status500_recent-window_packet_summary_20260301T074257Z.json`
- Verificación de agotamiento `status=404` y `zero_doc`:
  - `docs/etl/sprints/AI-OPS-351/evidence/senado_status404_recent-window_packet_summary_20260301T074257Z.json`
  - `docs/etl/sprints/AI-OPS-351/evidence/senado_zero_doc_recent-window_packet_summary_20260301T074257Z.json`
  - `docs/etl/sprints/AI-OPS-351/evidence/senado_lane_decision_ai_ops_351_20260301T074257Z.json`
- Estado/delta de cobertura:
  - `docs/etl/sprints/AI-OPS-351/evidence/initiative_doc_status_before_20260301T074257Z.json`
  - `docs/etl/sprints/AI-OPS-351/evidence/initiative_doc_status_after_20260301T074257Z.json`
  - `docs/etl/sprints/AI-OPS-351/evidence/initiative_doc_status_delta_ai_ops_351_20260301T074257Z.json`
  - `docs/etl/sprints/AI-OPS-351/evidence/senado_waf_block_profile_before_20260301T074257Z.json`
  - `docs/etl/sprints/AI-OPS-351/evidence/senado_waf_block_profile_after_20260301T074257Z.json`
  - `docs/etl/sprints/AI-OPS-351/evidence/senado_waf_block_profile_delta_ai_ops_351_20260301T074257Z.json`
- Gap archive consolidado:
  - `docs/etl/sprints/AI-OPS-351/evidence/senado_archive_gap_urls_20260301T074257Z.json`
  - `docs/etl/sprints/AI-OPS-351/exports/senado_archive_gap_urls_20260301T074257Z.csv`
