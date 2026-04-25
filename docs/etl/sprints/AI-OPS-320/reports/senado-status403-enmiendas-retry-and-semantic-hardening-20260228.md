# AI-OPS-320 - Retry dirigido `status=403` (enmiendas Senado) + hardening semántico

## Objetivo
Avanzar la fila `822` con una palanca nueva sobre cola accionable Senado (`enmiendas/index.html`, `status=403`, no-`ficopendataservlet`) y cerrar un gap de limpieza detectado en extracción semántica tras nuevas descargas.

## Ejecución
1. Baseline
- `report_initiative_doc_status.py` (before)
- `report_senado_waf_block_profile.py --only-linked-to-votes` (before)
- `report_senado_manual_capture_validity.py --strict` (`degraded`, `rc=4`)

2. Intento descartado (no accionable)
- Packet `global_enmiendas_vetos_xml status 500` (`80` URLs) terminó totalmente en `skipped_redundant_global_urls=80`; sin fetch efectivo.
- Se conserva como evidencia de descarte de cohorte no accionable.

3. Retry material (palanca nueva)
- Packet dirigido: `enmiendas/index.html` + `status=403` (80 URLs, 80 iniciativas).
- Comando:
  - `backfill-initiative-documents --doc-urls-file <packet> --retry-http-statuses 403 --archive-fallback --archive-fallback-http-statuses 403`
- Resultado:
  - `candidate_urls=80`, `urls_to_fetch=80`
  - `fetched_ok=3`, `archive_hits=3`, `archive_fetched_ok=3`, `text_documents_upserted=3`
  - `selected_scope_no_limit=true`

4. Post-proceso de estructura
- `backfill_initiative_doc_extractions.py --only-missing --initiative-source-ids senado_iniciativas`
- Resultado: `seen=3`, `upserted=3`, `needs_review=0`.

5. Limpieza semántica residual detectada y cerrada
- Observación post-retry: `44` filas con sujetos de navegación Senado (`Ir al Contenido`, `Preguntas frecuentes`, `Síguenos`, etc.).
- Hardening en extractor (`_looks_like_noisy_subject`) para filtrar navegación/chrome de página.
- Regresión nueva en tests: `test_noisy_senado_nav_sentence_falls_back_to_strong_title`.
- Reproceso completo Senado (`seen=3538`, `upserted=3538`) y verificación post: `noise_rows_total=0`.

## Delta medido
- Cobertura global iniciativas:
  - `downloaded_doc_links: 4347 -> 4350` (`+3`)
  - `missing_doc_links: 5206 -> 5203` (`-3`)
  - `missing_doc_links_actionable: 5022 -> 5019` (`-3`)
  - `effective_downloaded_doc_links_pct: 46.40 -> 46.43`
- Senado (`by_source`):
  - `downloaded_doc_links: 3535 -> 3538` (`+3`)
  - `missing_doc_links_actionable: 5022 -> 5019` (`-3`)
- Cola/WAF `only_linked_to_votes`:
  - `missing_urls: 1246 -> 1243` (`-3`)
  - `blocked_403_urls: 666 -> 586` (`-80`)
  - CSV cola (`incl. header`): `1247 -> 1244`
- Calidad semántica Senado:
  - ruido navegación observado pre-hardening: `44`
  - post-hardening: `0` (`delta=-44`)

## Validaciones
- `python3 -m unittest -v tests.test_backfill_initiative_doc_extractions` -> `Ran 9`, `OK`
- `DB_PATH=etl/data/staging/politicos-es.db just etl-tracker-status` -> `mismatches=0`, `done_zero_real=0`

## Evidencia
- `docs/etl/sprints/AI-OPS-320/evidence/initiative_doc_status_before_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_waf_block_profile_before_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_manual_capture_validity_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_global_enmiendas_status404_500_packet_summary_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_retry_global_enmiendas_status500_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_enmiendas_index_status403_packet_summary_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_retry_enmiendas_index_status403_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/initiative_doc_extractions_backfill_after_retry_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/initiative_doc_status_after_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/initiative_doc_status_delta_ai_ops_320_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_waf_block_profile_after_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_waf_block_profile_delta_ai_ops_320_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_tail_actionable_delta_ai_ops_320_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/initiative_doc_extractions_semantic_hardening_senado_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_extraction_nav_noise_post_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/senado_extraction_nav_noise_delta_ai_ops_320_20260228T230355Z.json`
- `docs/etl/sprints/AI-OPS-320/evidence/unittest_backfill_initiative_doc_extractions_20260228T230355Z.txt`
- `docs/etl/sprints/AI-OPS-320/evidence/tracker_status_20260228T230355Z.log`

## Estado
- `820/822`: siguen `PARTIAL` por bloqueo WAF residual, pero con mejora material de descarga y reducción de cola.
- Curación semántica Senado reforzada y mantenida en `DONE`.
