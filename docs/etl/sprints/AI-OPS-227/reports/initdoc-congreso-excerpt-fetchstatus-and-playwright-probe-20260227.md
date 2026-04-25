# AI-OPS-227 - Iniciativas: cierre de debt local (excerpts/fetch-status) + diagnóstico runtime Playwright

Fecha (UTC): 2026-02-27

## Objetivo
Seguir cerrando gaps controlables en `Textos de iniciativas (qué se votó)` sin depender de desbloqueo de red externo.

## Slice 1: limpieza/procesado local en Congreso

### 1) Backfill de excerpts (docs ya descargados)
- Comando:
  - `python3 scripts/backfill_initiative_doc_excerpts.py --db etl/data/staging/politicos-es.db --initiative-source-id congreso_iniciativas --limit 0`
- Resultado:
  - `seen=729`, `updated=729`, `skipped_missing_file=0`, `skipped_empty_text=0`, `pdf_parse_unavailable_or_empty=0`.

### 2) Backfill de fetch-status
- Comando:
  - `python3 scripts/backfill_initiative_doc_fetch_status.py --db etl/data/staging/politicos-es.db --initiative-source-id congreso_iniciativas --limit 0`
- Resultado:
  - `candidate_urls=157`, `candidate_refs_total=205`, `inserted_or_would_insert=157`.
  - Cobertura fetch-status en Congreso: `missing_fetch_status 205 -> 0`.

### 3) Delta de calidad (pre -> post)
- `downloaded_doc_links_with_excerpt`: `3393 -> 4205` (`+812`)
- `downloaded_doc_links_missing_excerpt`: `812 -> 0`
- `excerpt_coverage_pct`: `0.8069 -> 1.0`
- `doc_links_missing_fetch_status`: `205 -> 0`
- `fetch_status_coverage_pct`: `0.9765 -> 1.0`
- `missing_doc_links_actionable`: sin cambio (`4441`)
- `actionable_doc_links_closed_pct`: sin cambio (`0.4905`)

Resultado: se cierra la deuda local de calidad en docs descargados (excerpts/fetch-status), quedando el bloqueo residual únicamente en cola accionable de descarga Senado.

## Slice 2: probe acotado de runtime Playwright (1 intento)
- Comando (bounded):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --retry-forbidden --playwright-user-data-dir etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile --playwright-headless --limit-initiatives 5 --max-docs-per-initiative 1 --timeout 15`
- Resultado:
  - `fetched_ok=0`, `playwright_init_error` persiste (`AttributeError: PlaywrightContextManager ... _playwright`).
  - Failures replican `playwright init blocked` para todas las URLs del probe.

### Diagnóstico runtime adicional
- `playwright` driver bundled no levanta en este entorno:
  - `driver/node --version` => `rc=-9`
  - `driver node + cli.js --version` => `rc=-9`
- `sync_playwright()` con timeout controlado queda colgado hasta `TimeoutError: sync_playwright startup timeout`.

Conclusión operativa: el lane browser-assisted sigue bloqueado por bootstrap/runtime local de Playwright (antes de resolver bloqueo upstream), no solo por `403/500`.

## Estado de gate
- `quality-report --include-initiatives --enforce-gate` sigue en `rc=1`.
- Fallo residual único: `actionable_doc_links_closed_pct` (cola Senado).
- Export de cola accionable actualizado: `4441` filas (`senado_missing_actionable_latest.csv`, `4442` líneas con cabecera).
- Estado tracker al cierre del slice: `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-227/evidence/quality_initiatives_pre_latest.json`
- `docs/etl/sprints/AI-OPS-227/evidence/initdoc_excerpts_congreso_backfill_latest.json`
- `docs/etl/sprints/AI-OPS-227/evidence/initdoc_fetch_status_congreso_backfill_latest.json`
- `docs/etl/sprints/AI-OPS-227/evidence/quality_initiatives_post_latest.json`
- `docs/etl/sprints/AI-OPS-227/evidence/quality_initiatives_delta_pre_vs_post_latest.csv`
- `docs/etl/sprints/AI-OPS-227/evidence/quality_initiatives_post_enforce_latest.json`
- `docs/etl/sprints/AI-OPS-227/evidence/quality_initiatives_post_enforce_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-227/evidence/senado_playwright_probe_latest.log`
- `docs/etl/sprints/AI-OPS-227/evidence/playwright_driver_node_health_latest.json`
- `docs/etl/sprints/AI-OPS-227/evidence/playwright_sync_start_probe_latest.txt`
- `docs/etl/sprints/AI-OPS-227/evidence/playwright_sync_start_probe_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-227/evidence/senado_missing_actionable_export_latest.txt`
- `docs/etl/sprints/AI-OPS-227/exports/senado_missing_actionable_latest.csv`
- `docs/etl/sprints/AI-OPS-227/evidence/tracker_status_latest.log`
