# AI-OPS-291 - Hardening de queries alternativas BOE (delegación)

## Objetivo
Mejorar cobertura de scraping en la lane alternativa (AI-OPS-289/290) cuando las queries base devuelven `0` resultados en BOE.

## Cambios implementados
- `scripts/scrape_liberty_delegated_alternative_boe_candidates.py`
  - Para targets `boe_redirector_query` ya no depende solo de la query original.
  - Añade variantes de búsqueda por `rol+institución` usando `build_query_variants(...)` (mismo enfoque del lane principal).
  - Limita variantes por target (`--max-queries-per-query-target`) para mantener coste de red acotado.
  - Dedup por `(link_key, candidate_boe_id)` conservando el candidato con mayor `candidate_score`.
- `justfile`
  - Nueva variable `LIBERTY_DELEGATED_ALTERNATIVE_BOE_MAX_QUERIES_PER_QUERY_TARGET`.
  - Lanes `parl-scrape/check-liberty-delegated-alternative-boe-candidates` pasan el parámetro.
- Tests:
  - `tests/test_scrape_liberty_delegated_alternative_boe_candidates.py` actualizado para el nuevo contrato.

## Corrida real (AI-OPS-291)
- Input: `22` targets alternativos sobre `2` links pendientes.
- Scrape alternativo:
  - `candidate_rows_total: 6 -> 9` (`+3`)
  - `candidate_unique_boe_ids_total: 6 -> 9`
  - `query_candidates_total: 0 -> 6`
  - `direct_doc_candidates_total: 6 -> 3` (se prioriza cobertura mixta deduplicada)
  - `links_with_candidates_total=2/2`
- Replay (`review_assist -> auto_review -> pending_resolution -> apply(seed_out)`):
  - `approved_rows_total=0`
  - `pending_rows_total=2` (`delta=0` vs baseline AI-OPS-288)
  - razones residuales inalteradas:
    - `procedural_unit_not_found`
    - `role_topic_overlap_zero`

## Lectura operativa
- Se cierra una brecha de scraping/procesado (ya no estamos ciegos en queries BOE alternativas).
- El bloqueo residual queda confirmado como semántico de alineación de cargo, no de falta de captura.

## Evidencia
- `docs/etl/sprints/AI-OPS-291/evidence/liberty_delegated_alternative_boe_candidates_latest.json`
- `docs/etl/sprints/AI-OPS-291/evidence/liberty_delegated_alternative_boe_candidates_fail_latest.json`
- `docs/etl/sprints/AI-OPS-291/evidence/liberty_delegated_alternative_boe_candidates_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-291/evidence/liberty_delegated_person_window_auto_review_decisions_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-291/evidence/liberty_delegated_pending_resolution_review_queue_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-291/evidence/liberty_delegated_alternative_capture_replay_delta_latest.json`
- `docs/etl/sprints/AI-OPS-291/evidence/unittest_liberty_delegated_alternative_capture_and_boe_latest.txt`
- `docs/etl/sprints/AI-OPS-291/exports/liberty_delegated_alternative_boe_candidates_latest.csv`
