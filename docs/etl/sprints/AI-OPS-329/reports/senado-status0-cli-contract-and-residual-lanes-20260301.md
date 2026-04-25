# AI-OPS-329 - Contrato CLI `status=0` + continuidad de lane residual Senado

## Objetivo
Cerrar el hueco controlable detectado en AI-OPS-328 (CLI no aceptaba `--retry-http-statuses 0`) y ejecutar una iteración real de cola Senado para seguir avanzando scraping/procesado/estructuración con evidencia reproducible.

## Cambios de código
1. `etl/parlamentario_es/cli.py`
- `_parse_http_status_csv(...)` ahora acepta el centinela `0` solo cuando `allow_status_zero=True` (usado en `--retry-http-statuses`).
- Se mantiene el contrato estricto `100..599` para `--archive-fallback-http-statuses`.
- `_parse_http_status_maybe(...)` preserva `0` al parsear snapshots desde `--doc-urls-file`.

2. `etl/parlamentario_es/text_documents.py`
- `_normalize_http_status_filter(...)` acepta `0` para filtros de retry.
- `selected_doc_status_by_url` conserva `status=0` en snapshot para cohortes reproducibles.

3. Tests
- `tests/test_parl_cli_doc_urls_file.py`
  - retry acepta `0`.
  - archive fallback rechaza `0`.
  - `--doc-urls-file` preserva snapshot `last_http_status=0`.
- `tests/test_parl_text_documents.py`
  - nuevo caso: retry con `retry_http_statuses=(0,)` y snapshot estable.

## Ejecución AI-OPS-329
1. Baseline Senado (`status` + perfil WAF).
2. Export de cola accionable `status=0` (`217` filas).
3. Construcción de packet fresco `ficopendataservlet` excluyendo URLs ya usadas AI-OPS-324..328:
- `fresh_rows_total=0` (cohorte agotada).
4. Retry con soporte nativo CLI en pool `status=0`:
- comando con `--retry-http-statuses 0` ejecutado sobre `217` URLs del pool.
- resultado: `candidate_urls=217`, `urls_to_fetch=0`, `skipped_existing=217`, `skipped_retry_http_statuses=217`, `fetched_ok=0`.
5. Lane adicional `zero_doc` (controlable, no dependiente de pool fresco):
- packet `only-initiatives-without-any-doc`: `17` filas (`16` candidate URLs en ejecución).
- resultado: `fetched_ok=0`, `archive_lookup_attempted=16`, `archive_hits=0`, `text_documents_upserted=0`.
6. Post-proceso estructural:
- `backfill_initiative_doc_extractions --only-missing`: `seen=0`, `upserted=0`, `needs_review=0`.

## Delta medido (baseline -> post)
- Cobertura descarga Senado: sin cambio
  - `downloaded_doc_links=3599` (delta `0`)
  - `missing_doc_links_actionable=4958` (delta `0`)
  - `doc_links_missing_fetch_status=217` (delta `0`)
- Cola linked-to-votes: estable en volumen
  - `missing_urls=1182` (delta `0`)
  - `unknown_status_urls=217` (delta `0`)
  - `missing_initiatives=627` (delta `0`)
  - `zero_doc_initiatives=5` (delta `0`)
- Reclasificación marginal WAF
  - `blocked_403_urls: 331 -> 329` (delta `-2`)

## Estado de palanca manual
- Gate de validez de capturas manuales: `status=ok`, `usable_captures_total=2`, `strict rc=0`.
- Gate de vigencia de cookie seleccionada: `status=degraded`, `strict rc=4`, `no_new_lever=true` por `cookie_file_stale` (edad ~`242.677h` > `24h`).

## Conclusión
- El bloqueo técnico de herramienta quedó resuelto: `--retry-http-statuses 0` ya es usable y testeado.
- En datos, la cohorte `status=0 + ficopendataservlet` quedó agotada para packet fresco y la corrida residual no produjo descarga nueva.
- Se mantiene `PARTIAL` en la cola Senado; el siguiente paso de mayor probabilidad de delta sigue siendo retry acotado sobre `status=403` con cookie renovada no-stale.

## Evidencia
- `docs/etl/sprints/AI-OPS-329/evidence/unittest_status0_cli_and_retry_20260301T001838Z.txt`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_status0_actionable_pool_20260301T001838Z.stdout.log`
- `docs/etl/sprints/AI-OPS-329/exports/senado_status0_actionable_pool_20260301T001838Z.csv`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_ficopendataservlet_status0_fresh_packet_summary_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_retry_ficopendataservlet_status0_cli_supported_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_retry_status0_pool_cli_supported_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_retry_zero_doc_actionable_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/initiative_doc_extractions_backfill_after_retry_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/initiative_doc_status_before_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/initiative_doc_status_after_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/initiative_doc_status_delta_ai_ops_329_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_waf_block_profile_before_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_waf_block_profile_after_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_waf_block_profile_delta_ai_ops_329_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_manual_capture_validity_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_manual_capture_validity_20260301T001838Z.rc`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_cookie_lever_status_20260301T001838Z.json`
- `docs/etl/sprints/AI-OPS-329/evidence/senado_cookie_lever_status_20260301T001838Z.rc`
- `docs/etl/sprints/AI-OPS-329/evidence/tracker_status_20260301T001838Z.log`
