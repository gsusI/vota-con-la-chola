# AI-OPS-366 — Fallback directo `detalleiniciativa` (`status=404/403`) + probe Playwright

## Objetivo
Cerrar el TODO `856` implementando fallback determinista para la cohorte residual `detalleiniciativa` (`leg10 tipo610`, `18` URLs) y medir delta real en cobertura.

## Cambios de código (controlables)
- `etl/parlamentario_es/text_documents.py`
  - Nuevo helper `_senado_direct_variant_urls()` para derivar endpoints hermanos (`detalleiniciativa` <-> `ficopendataservlet tipoFich=3/12`).
  - Nuevo camino `direct_variant` en `backfill_initiative_documents_from_parl_initiatives` cuando `archive_first` no encuentra snapshot y la URL pertenece a cohorte bloqueada (`403/404`).
  - Nuevos contadores de observabilidad en salida JSON: `direct_variant_*`.
- `tests/test_parl_text_documents.py`
  - Nuevo test: `test_backfill_initiative_documents_archive_fallback_404_no_snapshot_uses_direct_variant`.
  - Ajuste de regresión para cohorte `403` archive-first manteniendo contrato estable.

## Validación unitaria
- `python3 -m unittest -v tests.test_parl_text_documents.TestParlTextDocuments.test_backfill_initiative_documents_archive_fallback_404_no_snapshot_uses_direct_variant ...` (5 tests)
- Resultado: `OK`.

## Ejecución real (DB principal)

### Run A — direct variant + cookie (`20260301T100159Z`)
- Cohorte fija: `docs/etl/sprints/AI-OPS-364/exports/senado_archive_gap_urls_20260301T092750Z.csv` (`18` URLs).
- Retry: `candidate_urls=18`, `fetched_ok=0`, `archive_hits=0`, `direct_variant_attempted_urls=18`, `direct_variant_candidate_urls=36`, `direct_variant_fetched_ok=0`, `failures=18`.
- Patrón dominante: `senado direct variants failed: HTTP Error 403: Forbidden`.

### Run B — Playwright (pre-ampliación guard) (`20260301T101143Z`)
- Retry: `candidate_urls=18`, `fetched_ok=0`, `archive_hits=0`, `direct_variant_attempted_urls=0`, `failures=18`.
- Resultado: sin conversión; el guard no activaba `direct_variant` para cohortes ya reclasificadas a `403`.

### Run C — Playwright v2 tras ampliar guard a `403/404` (`20260301T101836Z`)
- Retry: `candidate_urls=18`, `fetched_ok=0`, `archive_hits=0`, `direct_variant_attempted_urls=18`, `direct_variant_fetched_ok=0`, `failures=18`.
- Patrón dominante: `HTTPStatusError: HTTP 403 (playwright)` en variantes `tipoFich=3/12`.
- `playwright_init_error=null` (runtime sano; bloqueo en red/upstream).

## Delta KPI
- Cobertura: sin cambio neto.
  - `downloaded_doc_links: 5202 -> 5202`
  - `missing_doc_links_actionable: 4160 -> 4160`
  - `missing_urls: 384 -> 384`
- Reclasificación de cohorte residual:
  - `blocked_403_urls: 14 -> 32` (`+18`)
  - Bucket dominante en missing URLs pasa a `status=404=329` (desde `347`) con cohorte movida a `403`.

## Conclusión
El fallback técnico quedó implementado, testeado y ejecutado en producción, pero no convierte la cohorte residual: las variantes oficiales responden `403` de forma consistente incluso con Playwright+perfil persistente. Se cierra el objetivo como `NO_DELTA_WITH_EVIDENCE` y se mueve la lane a estrategia `status=403` (sesión/browser challenge) para esa cohorte.

## Evidencia
- `docs/etl/sprints/AI-OPS-366/evidence/senado_status404_direct_variant_retry_20260301T100159Z.json`
- `docs/etl/sprints/AI-OPS-366/evidence/senado_status404_direct_variant_delta_ai_ops_366_20260301T100159Z.json`
- `docs/etl/sprints/AI-OPS-366/evidence/senado_status404_direct_variant_playwright_retry_20260301T101143Z.json`
- `docs/etl/sprints/AI-OPS-366/evidence/senado_status404_direct_variant_playwright_v2_retry_20260301T101836Z.json`
- `docs/etl/sprints/AI-OPS-366/evidence/senado_status404_direct_variant_playwright_v2_delta_ai_ops_366_20260301T101836Z.json`
- `docs/etl/sprints/AI-OPS-366/evidence/e2e_tracker_status_with_tracker_20260301T100159Z.log`
