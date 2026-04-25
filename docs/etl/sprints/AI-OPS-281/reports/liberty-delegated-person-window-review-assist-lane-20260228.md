# AI-OPS-281 · Asistencia de revisión desde candidatos BOE

## Objetivo
Cerrar la brecha entre scraping BOE (AI-OPS-280) y loop review/apply (AI-OPS-278), produciendo una cola de asistencia a revisión con sugerencias normalizadas por `link_key`.

## Cambios
- Nuevo script: `scripts/export_liberty_delegated_person_window_review_assist_from_boe_candidates.py`.
  - Une `review_queue` y `boe_candidates` por `link_key`.
  - Filtra candidatos por score (`--min-candidate-score`) y limita por enlace (`--max-candidates-per-link`).
  - Normaliza fecha de publicación BOE a ISO (`candidate_publication_date_iso`).
  - Calcula señales de relevancia (`role_token_overlap`, `institution_token_overlap`) y bucket (`strong/medium/weak`).
  - Publica sugerencias para revisión (`suggested_reviewed_*`) sin aplicar cambios automáticos al seed.
  - Soporta gate estricto de volumen (`--strict-min-assist-rows`).
- Wiring en `justfile`:
  - `parl-export-liberty-delegated-person-window-review-assist`
  - `parl-check-liberty-delegated-person-window-review-assist`
  - variables `LIBERTY_DELEGATED_REVIEW_ASSIST_*`.
- Test añadido: `tests/test_export_liberty_delegated_person_window_review_assist_from_boe_candidates.py`.

## Corrida real

1) Export assist (`min_candidate_score=20`, `max_candidates_per_link=3`):
- `review_links_total=8`
- `review_links_with_candidates_total=5`
- `assist_rows_total=15`
- `relevance_bucket_counts={strong:0, medium:15, weak:0}`

2) Check estricto (pass-path):
- `strict_min_assist_rows=1` -> `status=ok`

3) Check estricto (fail-path contractual):
- `min_candidate_score=80`, `max_candidates_per_link=1`, `strict_min_assist_rows=1`
- resultado esperado: `assist_rows_total=0`, `rc=4`

4) Test focal:
- `python3 -m unittest tests/test_export_liberty_delegated_person_window_review_assist_from_boe_candidates.py`
- resultado: `Ran 1 test`, `OK`

## Resultado
- Slice cerrado: la cola de revisión ya tiene una vista procesada y priorizable con campos sugeridos listos para validación humana.
- El lane principal sigue `PARTIAL` hasta convertir parte de estas sugerencias en decisiones `approved` y aplicar sobre seed para reducir `actionable_queue_rows`.
