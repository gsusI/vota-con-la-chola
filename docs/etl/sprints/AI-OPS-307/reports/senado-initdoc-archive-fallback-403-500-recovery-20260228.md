# AI-OPS-307: Senado initdocs archive fallback extendido (403/500)

Fecha UTC: 2026-02-28
Objetivo: convertir una parte de la cola bloqueada de Senado en descarga efectiva con una palanca nueva reproducible (`archive_fallback` para `403/500`, además de `404`).

## Cambios de código

- `etl/parlamentario_es/text_documents.py`
  - Nuevo parámetro en `backfill_initiative_documents_from_parl_initiatives`: `archive_fallback_http_statuses`.
  - Normalización robusta de statuses (`100..599`, dedupe, fallback a default).
  - El fallback de Wayback deja de estar fijo a `404`; ahora usa la lista configurable.
  - El reporte de salida incluye `archive_fallback_http_statuses`.
- `etl/parlamentario_es/cli.py`
  - Nuevo flag CLI: `--archive-fallback-http-statuses` (default `404`).
  - Parse/validación estricta de CSV de statuses en `backfill-initiative-documents`.
- `justfile`
  - Nueva variable: `INITDOC_ARCHIVE_HTTP_STATUSES` (default `404`).
  - `parl-backfill-initiative-documents-archive` cableado al nuevo flag.
- `tests/test_parl_text_documents.py`
  - Nuevo test: `test_backfill_initiative_documents_archive_fallback_supports_custom_403_status`.

## Validación de tests

```bash
python3 -m unittest -v \
  tests.test_parl_text_documents.TestParlTextDocuments.test_backfill_initiative_documents_archive_fallback_recovers_prior_404 \
  tests.test_parl_text_documents.TestParlTextDocuments.test_backfill_initiative_documents_archive_fallback_no_snapshot_keeps_missing \
  tests.test_parl_text_documents.TestParlTextDocuments.test_backfill_initiative_documents_archive_fallback_supports_custom_403_status
```

Resultado: `OK`.

## Corrida real (bounded)

Comando ejecutado:

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --retry-forbidden \
  --archive-fallback \
  --archive-fallback-http-statuses 403,404,500 \
  --archive-timeout 12 \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
  --limit-initiatives 20 \
  --max-docs-per-initiative 1 \
  --timeout 15 \
  --snapshot-date 2026-02-28
```

Salida clave:

- `candidate_urls=40`
- `archive_lookup_attempted=40`
- `archive_hits=17`
- `archive_fetched_ok=17`
- `fetched_ok=17`
- `failures_total=23`

## Delta medido

Antes (AI-OPS-307 baseline) vs después del retry custom:

- `downloaded_doc_links` (overall): `4205 -> 4222` (`+17`)
- `missing_doc_links` (overall): `4527 -> 4510` (`-17`)
- `missing_doc_links_actionable` (overall): `4456 -> 4439` (`-17`)
- `effective_downloaded_doc_links_pct` (overall): `48.55 -> 48.75` (`+0.20 pp`)
- `linked_to_votes_with_downloaded_docs` (overall): `726 -> 743` (`+17`)

En Senado:

- `downloaded_doc_links`: `3393 -> 3410` (`+17`)
- `missing_doc_links`: `4527 -> 4510` (`-17`)
- `missing_doc_links_actionable`: `4456 -> 4439` (`-17`)
- `effective_downloaded_doc_links_pct`: `43.23 -> 43.45` (`+0.22 pp`)
- `linked_to_votes_with_downloaded_docs`: `622 -> 639` (`+17`)

Cola actionable linked-to-votes (export strict):

- filas CSV (`incluye cabecera`): `681 -> 664` (`680 -> 663` URLs)
- strict-empty: sigue abierto (`rc=4`).

Perfil WAF linked-to-votes post-run:

- `missing_urls=663`
- `blocked_403_urls=567`
- `blocked_500_urls=71`
- `zero_doc_initiatives=8` (antes `25`)

## Conclusión

Slice controlable entregado con mejora real en cobertura sin depender de una cookie usable nueva. El bloqueo remoto persiste, pero la nueva palanca `archive_fallback_http_statuses` convierte una parte del tail `403/500` en progreso descargable reproducible.
