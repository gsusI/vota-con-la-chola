# AI-OPS-353 — Conversion neta con palanca manual + archive fallback

## Objetivo
Completar el TODO de conversion (`row 844`) tras reabrir palanca manual en AI-OPS-352: obtener delta neta en `downloaded_doc_links`/`missing_doc_links_actionable`.

## Ejecucion
1. Baseline KPI/WAF (`quality-report` + `report_senado_waf_block_profile`) sobre `etl/data/staging/politicos-es.db`.
2. Retry manual canonical (`run_senado_manual_capture_retry_cycle --limit-initiatives 25 --strict-ready`) con cookie utilizable.
3. Intento adicional `status=404` linked-to-votes + `archive-fallback(403,404)` con `packet=25`.
4. Reintento acotado `packet=8` (misma lane) tras runtime alto del `packet=25`.
5. Post-proceso estructural (`backfill_initiative_doc_extractions --only-missing` + `backfill_initiative_doc_excerpts`) y snapshot final KPI/WAF.

## Resultado
- `run_senado_manual_capture_retry_cycle (limit=25)`: `status=ok`, `backfill.attempted=true`, `exit_code=0`, sin delta neta en esa pasada.
- `status404+archive packet=25`: interrumpido por runtime operativo alto (evidencia de interrupcion registrada).
- `status404+archive packet=8`: `fetched_ok=2`, `archive_hits=2`, `archive_fetched_ok=2`.
- Delta final (baseline -> post-process):
  - `downloaded_doc_links: 4802 -> 4804` (`+2`)
  - `missing_doc_links: 4751 -> 4749` (`-2`)
  - `missing_doc_links_actionable: 4561 -> 4559` (`-2`)
  - `missing_doc_links_actionable_linked_to_votes: 785 -> 783` (`-2`)
  - `missing_urls (linked_to_votes): 785 -> 783` (`-2`)
- Calidad post-proceso mantenida:
  - `downloaded_doc_links_missing_extraction: 2 -> 0` tras backfill (`upserted=2`, `needs_review=0`)
  - `downloaded_doc_links_missing_excerpt: 0` (sin cambios)

## Lectura operativa
- Se cumple el criterio de conversion neta del objetivo (`row 844`): hay mejora medible de cobertura bajo palanca manual.
- El bucket `403` aumenta (`+17`) por reclasificacion de faltantes; el cierre completo requiere seguir explotando `404` convertibles con control de runtime.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-353/evidence/senado_manual_capture_retry_cycle_20260301T075958Z.json`
- `docs/etl/sprints/AI-OPS-353/evidence/senado_status404_manual_cookie_archive_retry_packet8_20260301T080845Z.log`
- `docs/etl/sprints/AI-OPS-353/evidence/quality_initiatives_before_manual_retry_20260301T075958Z.json`
- `docs/etl/sprints/AI-OPS-353/evidence/quality_initiatives_after_archive_packet8_postprocess_20260301T081020Z.json`
- `docs/etl/sprints/AI-OPS-353/evidence/senado_waf_block_profile_before_manual_retry_20260301T075958Z.json`
- `docs/etl/sprints/AI-OPS-353/evidence/senado_waf_block_profile_after_archive_packet8_postprocess_20260301T081020Z.json`
- `docs/etl/sprints/AI-OPS-353/evidence/initiative_doc_extractions_backfill_after_archive_packet8_20260301T081020Z.json`
- `docs/etl/sprints/AI-OPS-353/evidence/senado_manual_cookie_archive_conversion_delta_ai_ops_353_20260301T081020Z.json`
