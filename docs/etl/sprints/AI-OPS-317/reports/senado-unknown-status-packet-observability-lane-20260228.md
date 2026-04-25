# AI-OPS-317 — Lane de estado desconocido (Senado) con retry acotado y cierre de observabilidad

## Objetivo

Reducir el gap de trazabilidad de la cola accionable Senado (`822`) convirtiendo URLs `unknown/no-status` en estados HTTP explicitos, sin abrir una nueva superficie de red.

## Preparacion

DB: `etl/data/staging/politicos-es.db`

- Se corrigio `scripts/export_missing_initiative_doc_urls.py` para que `--only-status 0` incluya tambien filas sin `document_fetches.last_http_status` (`COALESCE(...,0)=0`).
- Se valido con tests focales (`tests/test_export_missing_initiative_doc_urls.py`).
- Baseline pre-run (`only_linked_to_votes`):
  - `missing_urls=1252`
  - `unknown_status_urls=377`
  - cola accionable CSV: `1253` lineas (incluye cabecera).
- Packet desconocido generado con el fix:
  - `packet_rows_total=80`
  - `packet_unique_initiatives_total=80`
  - `packet_status_buckets`: `0=80`.

## Ejecucion

Retry unico con packet fijo (`--doc-urls-file`) y fallback archivistico:

- `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents ... --doc-urls-file senado_unknown_status_packet_20260228T223428Z.csv --archive-fallback --archive-fallback-http-statuses 403,404,500`

Resultado:

- `candidate_urls=80`
- `urls_to_fetch=80`
- `fetched_ok=0`
- `archive_lookup_attempted=80`
- `archive_hits=0`
- `archive_fetched_ok=0`
- `selected_scope_no_limit=true`
- `initiative_documents_upserted=80`
- `text_documents_upserted=0`
- `failures=30` (patron dominante: `archive fallback: no snapshot candidates`).

## Delta medido

Cobertura iniciativas (`before -> after`):

- `downloaded_doc_links: 4341 -> 4341` (`=0`)
- `missing_doc_links: 5212 -> 5212` (`=0`)
- `missing_doc_links_actionable: 5028 -> 5028` (`=0`)
- `doc_links_missing_fetch_status: 377 -> 297` (`-80`)
- `fetch_status_coverage_pct: 96.05 -> 96.89` (`+0.84pp`)

Senado (`before -> after`):

- `downloaded_doc_links: 3529 -> 3529` (`=0`)
- `missing_doc_links: 5212 -> 5212` (`=0`)
- `doc_links_missing_fetch_status: 377 -> 297` (`-80`)
- `missing_status_buckets(status=0): 491 -> 411` (`-80`)
- `missing_status_buckets(status=404): 187 -> 267` (`+80`)

Cola/WAF `only_linked_to_votes` (`before -> after`):

- `missing_urls: 1252 -> 1252` (`=0`)
- `blocked_403_urls: 666 -> 666` (`=0`)
- `blocked_500_urls: 101 -> 101` (`=0`)
- `unknown_status_urls: 377 -> 297` (`-80`)
- `zero_doc_initiatives: 6 -> 6` (`=0`)
- CSV cola accionable: `1253 -> 1253` lineas (incl. cabecera), `0`.

## Estado

- `visible_progress`: YES (cierre de observabilidad: `unknown -> status explicito` en `80` URLs, mejorando priorizacion y trazabilidad).
- Bloqueo externo persiste para cierre material de cola (`fetched_ok=0`, manual-capture strict `rc=4`).

## Evidencia

- `docs/etl/sprints/AI-OPS-317/evidence/senado_unknown_status_packet_summary_20260228T223428Z.json`
- `docs/etl/sprints/AI-OPS-317/exports/senado_unknown_status_packet_20260228T223428Z.csv`
- `docs/etl/sprints/AI-OPS-317/evidence/senado_retry_unknown_statuses_20260228T223428Z.json`
- `docs/etl/sprints/AI-OPS-317/evidence/initiative_doc_status_delta_ai_ops_317_20260228T223428Z.json`
- `docs/etl/sprints/AI-OPS-317/evidence/senado_waf_block_profile_delta_ai_ops_317_20260228T223428Z.json`
- `docs/etl/sprints/AI-OPS-317/evidence/senado_tail_actionable_delta_ai_ops_317_20260228T223428Z.json`
- `docs/etl/sprints/AI-OPS-317/evidence/senado_manual_capture_validity_20260228T223428Z.json`
- `docs/etl/sprints/AI-OPS-317/evidence/senado_manual_capture_validity_20260228T223428Z.rc`
- `docs/etl/sprints/AI-OPS-317/evidence/unittest_export_missing_initiative_doc_urls_20260228T223428Z.txt`
- `docs/etl/sprints/AI-OPS-317/evidence/tracker_status_20260228T223428Z.log`
