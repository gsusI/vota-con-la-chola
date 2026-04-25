# AI-OPS-231 - Senado: warmup Playwright no bloqueante + probe de cola accionable

Fecha: 2026-02-27

## Objetivo
Convertir la inicialización/warmup de Playwright en un paso `best-effort` para evitar bloqueos artificiales de scraping y medir impacto real sobre la cola accionable de Senado.

## Cambios implementados
- `etl/parlamentario_es/text_documents.py`
  - `_PlaywrightFetcher.get_bytes(...)` cambia warmup a modo no bloqueante:
    - si el warmup falla (`status>=400`, `None` o excepción), el fetch continúa con request directa.
    - se registra telemetría explícita en `playwright_runtime`: `warmup_attempted`, `warmup_status`, `warmup_error`, `warmup_ok`, `warmup_soft_failed`, `last_fetch_status`.
  - `backfill_initiative_documents_from_parl_initiatives(...)` ahora refresca `playwright_runtime` tras cada intento para reflejar estado real de warmup/fetch.
- `tests/test_parl_text_documents.py`
  - `test_playwright_fetcher_warmup_403_does_not_block_request`
  - `test_playwright_fetcher_warmup_exception_does_not_block_request`

## Validación técnica
- `python3 -m unittest tests/test_parl_text_documents.py tests/test_parl_quality.py tests/test_cli_quality_report.py`
- Resultado: `Ran 36 tests`, `OK`.

## Ejecución real (staging)
Comando:
- `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --retry-forbidden --playwright-user-data-dir etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile --playwright-headless --limit-initiatives 25 --max-docs-per-initiative 1 --timeout 15`

Resultado principal:
- `playwright_init_error=null`
- `playwright_runtime.fallback_applied=true`
- `playwright_runtime.warmup_soft_failed=true`
- `playwright_runtime.warmup_status=403`
- `playwright_runtime.last_fetch_status=403`
- `fetched_ok=0`

Interpretación:
- El lane ya no falla por warmup/bootstrap local.
- El bloqueo residual es estrictamente remoto/WAF en los endpoints objetivo (`HTTP 403` directo).

## Delta de cola accionable (scope `linked_to_votes`)
- Cola accionable linkeada:
  - pre: `680` URLs (`345` iniciativas)
  - post: `680` URLs (`345` iniciativas)
- Cola priorizada zero-doc (`max-urls-per-initiative=1`):
  - pre: `25` iniciativas
  - post: `25` iniciativas
- KPI quality (`linked_to_votes`):
  - `missing_doc_links_actionable_selected`: `680 -> 680`
  - `actionable_doc_links_closed_pct_selected`: `0.6726 -> 0.6726`

## Conclusión
Se cierra la deuda técnica de warmup bloqueante y se confirma con evidencia que el cuello de botella actual es WAF remoto, no runtime local. La cola accionable no se reduce en este slice.

## Evidencia
- `docs/etl/sprints/AI-OPS-231/evidence/senado_playwright_backfill_20260227_latest.json`
- `docs/etl/sprints/AI-OPS-231/evidence/senado_playwright_backfill_delta_20260227_latest.json`
- `docs/etl/sprints/AI-OPS-231/evidence/quality_initiatives_linked_pre_20260227_latest.json`
- `docs/etl/sprints/AI-OPS-231/evidence/quality_initiatives_linked_post_20260227_latest.json`
- `docs/etl/sprints/AI-OPS-231/evidence/unittest_parl_initiatives_playwright_lane_20260227_latest.txt`
- `docs/etl/sprints/AI-OPS-231/evidence/tracker_status_post_ai_ops_231_latest.log`
- `docs/etl/sprints/AI-OPS-231/exports/senado_missing_actionable_linked_pre_20260227_latest.csv`
- `docs/etl/sprints/AI-OPS-231/exports/senado_missing_actionable_linked_post_20260227_latest.csv`
- `docs/etl/sprints/AI-OPS-231/exports/senado_zero_doc_actionable_pre_20260227_latest.csv`
- `docs/etl/sprints/AI-OPS-231/exports/senado_zero_doc_actionable_post_20260227_latest.csv`
