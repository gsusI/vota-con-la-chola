# AI-OPS-328 - Lane de trazabilidad `status=0` (Senado) con retry acotado

## Objetivo
Reducir incertidumbre de la cola residual (`unknown_status_urls`) en Senado sobre `ficopendataservlet`, manteniendo la politica de un solo retry de red por sprint sin nueva palanca de cookies.

## Ejecucion
1. Baseline
- `report_initiative_doc_status.py` (before)
- `report_senado_waf_block_profile.py --only-linked-to-votes` (before)
- `report_senado_manual_capture_validity.py --strict` (`status=degraded`, `strict_fail_reasons=[no_usable_capture]`, `rc=4`)

2. Packet fresco `status=0`
- Pool base: cola accionable post-AI-OPS-327.
- Filtro: `doc_url LIKE %ficopendataservlet%`, `status=0`, excluyendo URLs ya usadas en AI-OPS-31x/32x/324/325/326/327.
- Resultado: `80` URLs / `80` iniciativas (`excluded_used_urls_total=803`).

3. Hallazgo de contrato CLI (documentado)
- Intento directo con `--retry-http-statuses 0` y `--archive-fallback-http-statuses 0` falla por validacion (`status HTTP fuera de rango 100..599`).
- Se registra como limitacion operativa reproducible de la herramienta.

4. Retry acotado valido para trazabilidad
- Comando aplicado: mismo `--doc-urls-file` **sin** filtro `--retry-http-statuses`.
- Resultado:
  - `candidate_urls=80`, `urls_to_fetch=80`
  - `fetched_ok=0`, `archive_hits=0`, `archive_fetched_ok=0`, `text_documents_upserted=0`
  - `skipped_redundant_global_urls=4`, `failures=30`

5. Post-proceso
- `backfill_initiative_doc_extractions --only-missing`: `seen=0`, `upserted=0`, `needs_review=0`.
- Sin regresion local (`downloaded_missing_excerpt=0`, `excerpt_coverage_pct=100.0`).

## Delta medido
- Cobertura de descarga: sin cambios (`downloaded_doc_links=4411`, `missing_doc_links_actionable=4958`).
- Cierre de observabilidad material:
  - `doc_links_missing_fetch_status: 297 -> 217` (`-80`)
  - `unknown_status_urls: 297 -> 217` (`-80`)
  - `blocked_403_urls: 251 -> 331` (`+80`) por reclasificacion de las URLs antes desconocidas.
- Cola `only_linked_to_votes`: `missing_urls` y CSV permanecen estables (`1182`, `1183` lineas incl. cabecera).

## Estado
- Sprint cierra con progreso visible en trazabilidad (menos `unknown`) sin mejora de descarga neta.
- Queda como accion tecnica recomendada: permitir `status=0` en `--retry-http-statuses` para evitar workaround con no-filter en futuras iteraciones.

## Evidencia
- `docs/etl/sprints/AI-OPS-328/evidence/initiative_doc_status_before_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/senado_waf_block_profile_before_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/senado_manual_capture_validity_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/senado_ficopendataservlet_status0_fresh_packet_summary_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/senado_retry_ficopendataservlet_status0_fresh_20260301T000708Z.json` (intento invalidado por contrato CLI)
- `docs/etl/sprints/AI-OPS-328/evidence/senado_retry_ficopendataservlet_status0_fresh_nofilter_20260301T000708Z.json` (corrida valida)
- `docs/etl/sprints/AI-OPS-328/evidence/initiative_doc_extractions_backfill_after_retry_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/initiative_doc_status_after_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/initiative_doc_status_delta_ai_ops_328_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/senado_waf_block_profile_after_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/senado_waf_block_profile_delta_ai_ops_328_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/senado_tail_actionable_delta_ai_ops_328_20260301T000708Z.json`
- `docs/etl/sprints/AI-OPS-328/evidence/senado_extraction_nav_noise_post_20260301T000708Z.json`
