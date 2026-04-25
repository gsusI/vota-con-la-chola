# AI-OPS-310 — Cohortes de retry Senado congeladas por snapshot (sin drift intra-sprint)

## Objetivo

Cerrar el TODO `831` del tracker: ejecutar retries comparables sobre una cohorte fija de `doc_url` y evitar que cambios de `document_fetches.last_http_status` entre intentos re-clasifiquen la cola.

## Cambios de código (repo-control)

- `etl/parlamentario_es/cli.py`
  - Nuevo flag `--doc-urls-file` en `backfill-initiative-documents`.
  - Parser de cohortes desde `TXT/CSV/JSON` con soporte de `doc_url` + `last_http_status/status`.
- `etl/parlamentario_es/text_documents.py`
  - `backfill_initiative_documents_from_parl_initiatives(...)` acepta:
    - `selected_doc_urls`
    - `selected_doc_status_by_url`
  - Filtro de cohorte fija aplicado sobre `candidate_urls`.
  - Uso de status snapshot (congelado) en:
    - filtro `retry_http_statuses`
    - filtro `skip_forbidden`/`archive_first`.
  - Nuevos contadores de trazabilidad:
    - `selected_doc_urls_total`
    - `selected_doc_urls_with_snapshot_status`
    - `selected_doc_urls_not_in_candidates`
    - `urls_filtered_by_selected_doc_urls`
    - `selected_doc_status_used_for_forbidden_filter`
    - `selected_doc_status_used_for_retry`
- `tests/test_parl_text_documents.py`
  - Nuevo test: `test_backfill_initiative_documents_retry_http_statuses_uses_snapshot_status_for_stable_cohort`.
  - Nuevo test: `test_backfill_initiative_documents_snapshot_status_stabilizes_forbidden_filter`.

## Validación local

- `python3 -m unittest -v tests.test_parl_text_documents`
  - `Ran 15 tests`, `OK`.
  - Evidencia: `docs/etl/sprints/AI-OPS-310/evidence/unittest_parl_text_documents_ai_ops_310_20260228T214135Z.txt`.

## Ejecución real (DB principal)

DB: `etl/data/staging/politicos-es.db`

1. Export de cohorte fija Senado (`40` URLs):
- `scripts/export_senado_waf_cohort_packets.py`
- Salidas:
  - `docs/etl/sprints/AI-OPS-310/evidence/senado_waf_packet_summary_20260228T213751Z.json`
  - `docs/etl/sprints/AI-OPS-310/exports/senado_waf_packet_20260228T213751Z.csv`

2. Replay doble con snapshot congelado (`--doc-urls-file`, `--retry-http-statuses 403`, `--refetch-existing`):
- Primer run: `senado_retry_snapshot_file_status403_refetch_first_20260228T214135Z.json`
- Segundo run: `senado_retry_snapshot_file_status403_refetch_second_20260228T214135Z.json`

Resultado comparado (first == second):
- `candidate_urls=40`
- `urls_to_fetch=40`
- `skipped_forbidden=0`
- `skipped_retry_http_statuses=0`
- `selected_doc_status_used_for_forbidden_filter=40`
- `selected_doc_status_used_for_retry=40`
- `fetched_ok=9`
- `archive_fetched_ok=9`

Lectura: el replay queda estable por snapshot y no deriva por cambios de status en DB entre corridas consecutivas.

## Post-proceso de estructuración

- Backfill de extracciones faltantes tras nuevas descargas:
  - `scripts/backfill_initiative_doc_extractions.py --only-missing`
  - Resultado: `seen=9`, `upserted=9`, `needs_review=0`.
  - Evidencia: `docs/etl/sprints/AI-OPS-310/evidence/initiative_doc_extractions_backfill_post_snapshot_lock_20260228T214135Z.json`.

- Estado post-slice (`report_initiative_doc_status.py`):
  - `total_doc_links=9553`
  - `downloaded_doc_links=4245`
  - `missing_doc_links=5308`
  - `missing_doc_links_actionable=5091`
  - `effective_downloaded_doc_links_pct=45.47`
  - `extraction_coverage_pct=100.0`.
  - Evidencia: `docs/etl/sprints/AI-OPS-310/evidence/initiative_doc_status_post_snapshot_lock_extractions_20260228T214135Z.json`.

## Estado del slice

- `visible_progress`: YES (mecanismo contractual + validación unitaria + replay real estable + nuevas descargas + post-proceso cerrado).
- `tracker_row_831`: listo para pasar a `DONE`.
- `822` permanece `PARTIAL`: persiste cola Senado/WAF, pero ahora con lane de retry reproducible sin drift.
