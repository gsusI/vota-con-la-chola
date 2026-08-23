# AI-OPS-309 — Lane `retry_http_statuses` en Senado + diagnóstico de drift de estado

## Objetivo

Ejecutar y validar en DB real la nueva palanca `--retry-http-statuses` para reintentos dirigidos de `senado_iniciativas`, con evidencia de impacto en cola accionable y KPIs de cobertura.

## Cambios de código (repo-control)

- `etl/parlamentario_es/text_documents.py`
  - Nuevo filtro `retry_http_statuses` en `backfill_initiative_documents_from_parl_initiatives(...)`.
  - Métricas de salida: `retry_http_statuses`, `skipped_retry_http_statuses`.
- `etl/parlamentario_es/cli.py`
  - Nuevo flag: `--retry-http-statuses` (CSV).
- `tests/test_parl_text_documents.py`
  - Test nuevo: `test_backfill_initiative_documents_retry_http_statuses_filters_queue`.
- Validación local de regresión:
  - `python3 -m unittest -v tests.test_parl_text_documents.TestParlTextDocuments` -> `exit 0` (`docs/etl/sprints/AI-OPS-309/evidence/unittest_parl_text_documents_ai_ops_309_20260228T235500Z.txt`).

## Ejecución real (DB principal)

DB: `etl/data/staging/politicos-es.db`

1. Precheck de palanca manual (cookie capture)
- `report_senado_manual_capture_validity.py --strict`
- Resultado: `status=degraded`, `usable_captures_total=0`, `rc=4`.

2. Retry dirigido por status `404` (archivo sólo `404`)
- `backfill-initiative-documents ... --retry-http-statuses 404 --archive-fallback-http-statuses 404`
- Resultado: `urls_to_fetch=112`, `fetched_ok=0`, `archive_lookup_attempted=0`, `archive_fetched_ok=0`.

3. Retry dirigido por status `500` (archivo sólo `500`)
- `backfill-initiative-documents ... --retry-http-statuses 500 --archive-fallback-http-statuses 500`
- Resultado: `urls_to_fetch=78`, `fetched_ok=0`, `archive_lookup_attempted=0`, `archive_fetched_ok=0`, `failures=30` (`HTTP 403`).

4. Retry `500` con archivo `403,500` (validación de drift)
- `backfill-initiative-documents ... --retry-http-statuses 500 --archive-fallback-http-statuses 403,500`
- Resultado: `urls_to_fetch=0`, `fetched_ok=0`, `skipped_retry_http_statuses=759`.

## Resultado medido (before -> after)

### Cobertura iniciativas docs (`report_initiative_doc_status.py`)

- Overall:
  - `downloaded_doc_links`: `4236 -> 4236` (`delta 0`)
  - `missing_doc_links`: `4496 -> 4614` (`+118`)
  - `missing_doc_links_actionable`: `4425 -> 4543` (`+118`)
  - `linked_to_votes_with_downloaded_docs`: `745 -> 745` (`delta 0`)
  - `effective_downloaded_doc_links_pct`: `48.91 -> 48.25`
- Senado:
  - `downloaded_doc_links`: `3424 -> 3424` (`delta 0`)
  - `missing_doc_links`: `4496 -> 4614` (`+118`)
  - `missing_doc_links_actionable`: `4425 -> 4543` (`+118`)
  - `effective_downloaded_doc_links_pct`: `43.62 -> 42.98`

Lectura: no hubo nueva descarga (`fetched_ok=0`), pero se estructuraron enlaces faltantes (upsert de relaciones) en cola real.

### Perfil WAF (`report_senado_waf_block_profile.py --only-linked-to-votes`)

- `missing_urls`: `649 -> 767` (`+118`)
- `blocked_403_urls`: `475 -> 678` (`+203`)
- `blocked_500_urls`: `60 -> 36` (`-24`)
- `unknown_status_urls`: `0 -> 51` (`+51`)
- `zero_doc_initiatives`: `6 -> 6` (`delta 0`)

Lectura: el bloqueo persiste y se observa desplazamiento de cohorte (`500 -> 403`) tras retries dirigidos.

### Cola accionable exportada

- `senado_tail_actionable_before`: `650` filas (incluye cabecera)
- `senado_tail_actionable_after`: `767` filas (incluye cabecera)
- Delta: `+117` filas.

### Gate tracker

- `DB_PATH=etl/data/staging/politicos-es.db just etl-tracker-status`
- Resultado: `mismatches=0`, `done_zero_real=0`.

## Estado del slice

- `visible_progress`: YES (palanca `retry_http_statuses` implementada + validada en DB real + evidencia de comportamiento por cohorte).
- `closure`: NO para cola Senado (`strict-empty` sigue abierto; capture gate manual sigue `degraded`).

## Siguiente paso recomendado

Ejecutar un único retry de sprint sobre cola congelada por cohorte (snapshot exportado) para evitar drift intra-sprint de `last_http_status`, y mantener comparación delta contra AI-OPS-309.
