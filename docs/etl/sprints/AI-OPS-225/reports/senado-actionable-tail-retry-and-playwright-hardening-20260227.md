# AI-OPS-225 — Cola accionable Senado: retry de red + hardening Playwright

Fecha: 2026-02-27 (UTC)

## Objetivo
Reducir `missing_doc_links_actionable` en `senado_iniciativas` y cerrar brechas técnicas que bloqueaban reintentos reproducibles.

## Comandos ejecutados
1. Baseline de estado/quality/export:
   - `scripts/report_initiative_doc_status.py`
   - `scripts/ingestar_parlamentario_es.py quality-report --include-initiatives`
   - `scripts/export_missing_initiative_doc_urls.py --only-actionable-missing`
2. Retry red real (sin cookie, con `archive-fallback`, `include-unlinked`):
   - `scripts/ingestar_parlamentario_es.py backfill-initiative-documents --initiative-source-ids senado_iniciativas --include-unlinked --retry-forbidden --archive-fallback ...`
3. Retry con `cookie-file` (sin link-backfill):
   - `scripts/ingestar_parlamentario_es.py backfill-initiative-documents --initiative-source-ids senado_iniciativas --skip-link-backfill --retry-forbidden --cookie-file ...`
4. Retry con `playwright-user-data-dir` (sin link-backfill):
   - `scripts/ingestar_parlamentario_es.py backfill-initiative-documents --initiative-source-ids senado_iniciativas --skip-link-backfill --retry-forbidden --playwright-user-data-dir ...`
5. Hardening de código + regresión:
   - `etl/parlamentario_es/text_documents.py`
   - `tests/test_parl_text_documents.py`
   - `python3 -m unittest tests.test_parl_text_documents`

## Resultado (pre -> final)
- `downloaded_doc_links`: `4041 -> 4041` (`delta=0`)
- `missing_doc_links`: `4676 -> 4732` (`delta=+56`)
- `missing_doc_links_actionable`: `4599 -> 4655` (`delta=+56`)
- `actionable_doc_links_closed_pct`: `0.4724 -> 0.4694`

Estado Senado (final):
- `missing_doc_links_status_buckets`: `403=2546`, `500=1844`, `0=246`, `200=93`, `404=3`
- `global_enmiendas_vetos_analysis.actionable_missing_count`: `46`

## Hallazgos técnicos
- Retry sin cookie y con cookie no descargó payloads (`fetched_ok=0`) y confirmó bloqueo dominante `403/500`.
- Path Playwright quedaba en estado parcial tras fallo de init y producía cascada de errores por URL.
- Se corrigió el fetcher para:
  - limpiar estado en init fallido,
  - no reutilizar instancias parcialmente inicializadas,
  - bloquear reintentos de init tras el primer fallo (`playwright_init_error` + `playwright init blocked`).

## Evidencia principal
- `docs/etl/sprints/AI-OPS-225/evidence/initiative_doc_status_pre_20260227T014731Z.json`
- `docs/etl/sprints/AI-OPS-225/evidence/quality_initiatives_pre_20260227T014731Z.json`
- `docs/etl/sprints/AI-OPS-225/evidence/senado_backfill_docs_run_20260227T074122Z.log`
- `docs/etl/sprints/AI-OPS-225/evidence/senado_backfill_docs_cookiefile_run_20260227T075634Z.log`
- `docs/etl/sprints/AI-OPS-225/evidence/senado_backfill_docs_playwright_run_20260227T075847Z.log`
- `docs/etl/sprints/AI-OPS-225/evidence/senado_backfill_docs_playwright_run_circuit_20260227T080231Z.log`
- `docs/etl/sprints/AI-OPS-225/evidence/quality_initiatives_final_20260227T080442Z.json`
- `docs/etl/sprints/AI-OPS-225/evidence/quality_initiatives_delta_pre_vs_final_latest.csv`
- `docs/etl/sprints/AI-OPS-225/evidence/unittest_parl_text_documents_20260227T080612Z.txt`

## Siguiente paso recomendado
- No ampliar cola con `--include-unlinked` en runs de drenaje.
- Reintento acotado por sprint con nueva palanca real (captura cookie/perfil fresca) y luego `quality-report --include-initiatives --enforce-gate`.
