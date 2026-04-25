# AI-OPS-290 - Replay de captura alternativa delegada (scrape -> assist -> auto-review -> apply)

## Objetivo
Ejecutar el loop completo sobre los `2` pendientes residuales de delegación usando los targets alternativos de AI-OPS-289 y dejar el resultado estructurado y reproducible.

## Cambios implementados
- Nuevo scraper de candidatos BOE desde targets alternativos:
  - `scripts/scrape_liberty_delegated_alternative_boe_candidates.py`
  - Convierte `boe_redirector_query` y `boe_direct_doc` en CSV compatible con el lane existente (`review_assist`).
  - Incluye métricas de fetch, cobertura por `link_key`, dedupe por `(link_key, candidate_boe_id)` y gates strict (`strict_min_candidates`, `strict_min_links_with_candidates`).
- Hardening de datos en lane alternativo:
  - `scripts/export_liberty_delegated_alternative_capture_targets.py` ahora propaga `candidate_publication_date_iso` para `boe_direct_doc`.
  - El scraper convierte ISO a `dd/mm/yyyy` para que `review_assist` derive `candidate_publication_date_iso` y no pierda `evidence_date`.
- Wiring `justfile`:
  - `parl-scrape-liberty-delegated-alternative-boe-candidates`
  - `parl-check-liberty-delegated-alternative-boe-candidates`
- Tests:
  - `tests/test_scrape_liberty_delegated_alternative_boe_candidates.py`
  - Ajuste de regresión en `tests/test_export_liberty_delegated_alternative_capture_targets.py` (contrato de columnas extendido).

## Corrida reproducible (AI-OPS-290)
1. Export/check de targets alternativos (AI-OPS-289) con fecha propagada.
2. Scrape/check de candidatos alternativos BOE.
3. Replay sobre cola residual (`2` links):
   - `export_liberty_delegated_person_window_review_assist_from_boe_candidates.py`
   - `export_liberty_delegated_person_window_auto_review_decisions.py`
   - `export_liberty_delegated_pending_resolution_review_queue.py`
   - `apply_liberty_delegated_person_window_reviews.py` a `seed_out` aislado

## Resultado
- Scrape alternativo:
  - `targets_total=22`
  - `fetch_ok_total=18`, `fetch_error_total=4` (`status=0` en `4` targets institucionales)
  - `links_with_candidates_total=2/2`
  - `candidate_rows_total=6`, `candidate_unique_boe_ids_total=6`
- Replay:
  - `review_assist`: `assist_rows_total=6`, `review_links_with_candidates_total=2/2`
  - `auto_review`: `approved_rows_total=0`, `pending_rows_total=2`
  - `rows_missing_required_evidence_date_total=0` (mejora frente al intento previo sin fecha propagada)
  - `rows_missing_role_alignment_total=2`
  - `pending_reason_counts` final:
    - `auto_assist:role_alignment_failed:procedural_unit_not_found`
    - `auto_assist:role_alignment_failed:role_topic_overlap_zero`
- Delta vs baseline AI-OPS-288:
  - `pending_rows_total: 2 -> 2` (`delta=0`)
  - se elimina el artefacto transitorio `missing_evidence_date_for_required_field` gracias al fix de fecha.

## Lectura operativa
- El lane de captura alternativa queda operacional y trazable (scrape + estructuración + replay + apply validado).
- La brecha residual ya no es de captura/fecha, sino semántica de alineación de cargo:
  - `procedural_unit_not_found`
  - `role_topic_overlap_zero`

## Evidencia
- `docs/etl/sprints/AI-OPS-290/evidence/liberty_delegated_alternative_boe_candidates_latest.json`
- `docs/etl/sprints/AI-OPS-290/evidence/liberty_delegated_alternative_boe_candidates_fail_latest.json`
- `docs/etl/sprints/AI-OPS-290/evidence/liberty_delegated_alternative_boe_candidates_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-290/evidence/liberty_delegated_person_window_review_assist_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-290/evidence/liberty_delegated_person_window_auto_review_decisions_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-290/evidence/liberty_delegated_pending_resolution_review_queue_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-290/evidence/liberty_delegated_person_window_auto_review_apply_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-290/evidence/liberty_delegated_alternative_capture_replay_delta_latest.json`
- `docs/etl/sprints/AI-OPS-290/evidence/unittest_liberty_delegated_alternative_boe_candidates_latest.txt`
- `docs/etl/sprints/AI-OPS-290/evidence/unittest_liberty_delegated_alternative_capture_and_boe_latest.txt`
- `docs/etl/sprints/AI-OPS-290/exports/liberty_delegated_alternative_boe_candidates_latest.csv`
