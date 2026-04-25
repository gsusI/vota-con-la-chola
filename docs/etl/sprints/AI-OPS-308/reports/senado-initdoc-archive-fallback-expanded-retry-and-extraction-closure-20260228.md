# AI-OPS-308 — Senado initdoc: retry ampliado con archive fallback + cierre de extracción

Fecha: 2026-02-28
DB: `etl/data/staging/politicos-es.db`

## Objetivo
Reducir la cola accionable Senado (`row 822`) con un único retry acotado usando la palanca `archive_fallback_http_statuses=403,404,500` y cerrar la regresión de extracción semántica abierta por nuevas descargas.

## Comandos ejecutados

```bash
python3 scripts/report_senado_manual_capture_validity.py \
  --captures-glob 'etl/data/raw/manual/senado*_cookie_refresh_*.meta.json' \
  --cookie-domain-contains senado.es --min-captures 1 --strict \
  --out docs/etl/sprints/AI-OPS-308/evidence/senado_manual_capture_validity_20260228T220500Z.json

python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill --retry-forbidden \
  --archive-fallback --archive-fallback-http-statuses 403,404,500 \
  --limit-initiatives 80 --max-docs-per-initiative 1 --timeout 15

python3 scripts/backfill_initiative_doc_extractions.py \
  --db etl/data/staging/politicos-es.db \
  --doc-source-id parl_initiative_docs \
  --initiative-source-ids senado_iniciativas \
  --only-missing
```

## Resultado

- Gate de captura manual: `status=degraded`, `usable_captures_total=0`, `strict rc=4`.
- Retry Senado (acotado):
  - `initiatives_seen=80`
  - `candidate_urls=112`
  - `archive_lookup_attempted=112`
  - `archive_hits=14`
  - `archive_fetched_ok=14`
  - `fetched_ok=14`
  - `playwright_init_error=null`
- Backfill de extracción post-retry:
  - `seen=31`, `upserted=31`, `needs_review=0`

## Delta principal (before -> after)

- Cobertura docs (overall):
  - `downloaded_doc_links`: `4222 -> 4236` (`+14`)
  - `missing_doc_links`: `4510 -> 4496` (`-14`)
  - `missing_doc_links_actionable`: `4439 -> 4425` (`-14`)
  - `linked_to_votes_with_downloaded_docs`: `743 -> 745` (`+2`)
  - `effective_downloaded_doc_links_pct`: `48.75 -> 48.91` (`+0.16 pp`)
- Senado:
  - `downloaded_doc_links`: `3410 -> 3424` (`+14`)
  - `missing_doc_links_actionable`: `4439 -> 4425` (`-14`)
  - `linked_to_votes_with_downloaded_docs`: `639 -> 641` (`+2`)
  - `effective_downloaded_doc_links_pct`: `43.45 -> 43.62` (`+0.17 pp`)
- WAF / cola linked-to-votes:
  - `missing_urls`: `663 -> 649` (`-14`)
  - `blocked_403_urls`: `567 -> 475` (`-92`)
  - `blocked_500_urls`: `71 -> 60` (`-11`)
  - `zero_doc_initiatives`: `8 -> 6` (`-2`)
  - cola CSV accionable: `663 -> 649` filas (`-14`)
- Procesamiento local post-descarga:
  - `downloaded_missing_extraction`: `31 -> 0`
  - `extraction_coverage_pct`: `99.6 -> 100.0`

## Estado de bloqueo
Persiste bloqueo upstream/WAF en Senado (fila sigue `PARTIAL`): el `strict-empty` de cola accionable continúa abierto (`rc=4`).

## Evidencia

- `docs/etl/sprints/AI-OPS-308/evidence/senado_manual_capture_validity_20260228T220500Z.json`
- `docs/etl/sprints/AI-OPS-308/evidence/senado_retry_archive_custom_statuses_attempt_20260228T221500Z.txt`
- `docs/etl/sprints/AI-OPS-308/evidence/initiative_doc_status_before_20260228T221000Z.json`
- `docs/etl/sprints/AI-OPS-308/evidence/initiative_doc_status_after_20260228T222400Z.json`
- `docs/etl/sprints/AI-OPS-308/evidence/initiative_doc_status_after_extraction_20260228T223000Z.json`
- `docs/etl/sprints/AI-OPS-308/evidence/initiative_doc_status_delta_ai_ops_308_20260228T223100Z.json`
- `docs/etl/sprints/AI-OPS-308/evidence/senado_waf_block_profile_before_20260228T221000Z.json`
- `docs/etl/sprints/AI-OPS-308/evidence/senado_waf_block_profile_after_20260228T222400Z.json`
- `docs/etl/sprints/AI-OPS-308/exports/senado_tail_actionable_before_20260228T221000Z.csv`
- `docs/etl/sprints/AI-OPS-308/exports/senado_tail_actionable_after_20260228T222400Z.csv`
- `docs/etl/sprints/AI-OPS-308/evidence/just_parl_check_missing_initdoc_urls_actionable_empty_after_20260228T222400Z.rc`
- `docs/etl/sprints/AI-OPS-308/evidence/initiative_doc_extractions_backfill_after_retry_20260228T222900Z.json`
- `docs/etl/sprints/AI-OPS-308/evidence/tracker_status_20260228T223200Z.log`
