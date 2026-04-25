# AI-OPS-230 - Runtime Playwright Senado: fallback Node y cierre de bootstrap local

Fecha: 2026-02-27

## Objetivo
Cerrar el bloqueo local de arranque de Playwright (`AttributeError ... _playwright`) para que el lane de descarga Senado quede limitado al bloqueo remoto (WAF), no al runtime local.

## Cambios implementados
- `etl/parlamentario_es/text_documents.py`
  - Nuevo helper `_ensure_playwright_nodejs_runtime(...)`:
    - sonda salud del driver bundled de Playwright.
    - si está ausente/no sano (incluye probe indeterminado) y `node` del sistema valida `cli.js`, fija `PLAYWRIGHT_NODEJS_PATH` automáticamente.
  - `backfill_initiative_documents_from_parl_initiatives` ahora expone metadatos `playwright_runtime` en el JSON de salida.
- Tests:
  - `tests/test_parl_text_documents.py` añade cobertura de fallback por driver con `rc!=0`, por probe indeterminado y por respeto de env ya fijado.

## Validación
- Unit tests:
  - `python3 -m unittest tests/test_parl_text_documents.py`
  - Resultado: `Ran 9 tests`, `OK`.
- Probe real (staging):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --retry-forbidden --playwright-user-data-dir etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile --playwright-headless --limit-initiatives 5 --max-docs-per-initiative 1 --timeout 15`
  - Resultado clave:
    - `playwright_init_error=null`
    - `playwright_runtime.fallback_applied=true`
    - `playwright_runtime.effective_nodejs_path=<abs>/node`
    - fallos remotos esperados: `HTTPStatusError warmup failed status=403`

## Conclusión operativa
El KPI de bootstrap local queda cerrado: Playwright inicializa correctamente con fallback automático. El gap abierto del lane pasa a ser puramente remoto (WAF 403), por lo que el ítem se actualiza a `PARTIAL`.

## Evidencia
- `docs/etl/sprints/AI-OPS-230/evidence/senado_playwright_runtime_probe_backfill_20260227_latest.json`
- `docs/etl/sprints/AI-OPS-230/evidence/senado_playwright_runtime_probe_summary_20260227_latest.json`
- `docs/etl/sprints/AI-OPS-230/evidence/unittest_playwright_runtime_fallback_20260227_latest.txt`
- `docs/etl/sprints/AI-OPS-230/evidence/tracker_status_post_ai_ops_230_latest.log`
