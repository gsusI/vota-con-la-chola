# AI-OPS-311 — Fix de scope en `--doc-urls-file` + retry archivístico acotado Senado

## Objetivo

Avanzar `822` sin abrir nuevo churn estructural: corregir la lane de cohorte snapshot para que no expanda mappings fuera del paquete seleccionado y ejecutar un único retry acotado por sprint con medición before/after.

## Cambios de código (repo-control)

- `etl/parlamentario_es/text_documents.py`
  - Cuando se usa `selected_doc_urls` (vía `--doc-urls-file`), el scope aplica también al upsert de `parl_initiative_documents`.
  - Se añade métrica `doc_links_filtered_by_selected_doc_urls` para trazabilidad del recorte.
- `tests/test_parl_text_documents.py`
  - Nuevo test: `test_backfill_initiative_documents_selected_doc_urls_limits_mapping_upserts`.
  - Suite completa del módulo en verde.

## Validación local

- `python3 -m unittest -v tests.test_parl_text_documents`
  - `Ran 16 tests`, `OK`.
  - Evidencia: `docs/etl/sprints/AI-OPS-311/evidence/unittest_parl_text_documents_ai_ops_311_20260228T215008Z.txt`.

## Ejecución operativa (DB principal)

DB: `etl/data/staging/politicos-es.db`

1. Gate de captura manual (pre-retry)
- `report_senado_manual_capture_validity --strict`
- Resultado: `status=degraded`, `captures_total=4`, `usable_captures_total=0`, `strict rc=4`.
- Conclusión: no hay palanca de cookie utilizable; se ejecuta un único retry archivístico acotado.

2. Paquete de cohorte fija
- Export: `scripts/export_senado_waf_cohort_packets.py`
- Cohorte seleccionada: `60` URLs (`top-2` cohortes + priorización zero-doc).

3. Retry acotado (una corrida)
- Comando base: `backfill-initiative-documents --doc-urls-file <packet.csv> --retry-http-statuses 403 --archive-fallback --archive-fallback-http-statuses 403 --skip-link-backfill`
- Resultado:
  - `doc_links_seen=60`
  - `candidate_urls=60`
  - `urls_to_fetch=6`
  - `fetched_ok=2` (`archive_fetched_ok=2`)
  - `initiative_documents_upserted=60`
  - `doc_links_filtered_by_selected_doc_urls=1377`
  - `urls_filtered_by_selected_doc_urls=1377`
- Lectura: el fix de scope evita inflación de mapping fuera del paquete y mantiene retry reproducible sobre cohorte fija.

4. Post-proceso de estructuración
- `backfill_initiative_doc_extractions --only-missing`
- Resultado: `downloaded_missing_extraction` permanece `0`.

## Delta before/after

Fuente: `initiative_doc_status_delta_ai_ops_311_20260228T215008Z.json`.

- Global:
  - `downloaded_doc_links`: `4245 -> 4247` (`+2`)
  - `missing_doc_links`: `5308 -> 5306` (`-2`)
  - `missing_doc_links_actionable`: `5091 -> 5089` (`-2`)
  - `effective_downloaded_doc_links_pct`: `45.47 -> 45.49` (`+0.02`)
- Senado:
  - `downloaded_doc_links`: `3433 -> 3435` (`+2`)
  - `missing_doc_links_actionable`: `5091 -> 5089` (`-2`)
  - `linked_to_votes_with_downloaded_docs`: `641 -> 641` (`delta 0`)
- WAF profile (`only_linked_to_votes`):
  - `missing_urls`: `1315 -> 1313` (`-2`)
  - `blocked_403_urls`: `725 -> 719` (`-6`)
  - `missing_initiatives`: `627 -> 627` (`delta 0`)
- Cola accionable CSV (`linked_to_votes`, incluye cabecera):
  - `1316 -> 1314` (`-2`).

## Estado del slice

- `visible_progress`: YES (fix de no-inflación + retry acotado + recuperación real + post-proceso cerrado).
- `822`: sigue `PARTIAL` por bloqueo WAF/cookie (sin captura usable), pero con mejora material y lane estable.
