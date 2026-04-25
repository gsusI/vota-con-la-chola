# AI-OPS-282 · Autorrevisión asistida + apply parcial de cola delegada

## Objetivo
Convertir la asistencia AI-OPS-281 en decisiones reproducibles no vacías y medir impacto real sobre la cola accionable de regulación delegada.

## Cambios
- Nuevo script: `scripts/export_liberty_delegated_person_window_auto_review_decisions.py`.
  - Une `review_queue` + `review_assist` por `link_key`.
  - Emite decisiones conservadoras (`approved/pending`) según razones accionables y campos requeridos.
  - Exige señal mínima por score (`--min-candidate-score`) y límite por enlace (`--max-candidates-per-link`).
  - Incluye gate estricto (`--strict-min-approved-rows`) para fail-fast contractual.
- Hardening adicional en scraping BOE:
  - `scripts/scrape_liberty_delegated_person_window_boe_candidates.py` mejora extracción de persona para patrones `nombramiento como ... de don/doña` y limpieza de puntuación.
- Wiring en `justfile`:
  - `parl-export-liberty-delegated-person-window-auto-review-decisions`
  - `parl-check-liberty-delegated-person-window-auto-review-decisions`
  - variables `LIBERTY_DELEGATED_AUTO_REVIEW_*`
- Tests añadidos/actualizados:
  - `tests/test_export_liberty_delegated_person_window_auto_review_decisions.py`
  - `tests/test_scrape_liberty_delegated_person_window_boe_candidates.py` (casos nuevos de extracción)

## Corrida real

1) Export/check de decisiones auto:
- `rows_total=8`
- `approved_rows_total=8`
- `pending_rows_total=0`
- `rows_missing_candidate_total=0`
- gate estricto pass: `strict_min_approved_rows=1`
- fail-path contractual: `strict_min_approved_rows=9`, `rc=4`

2) Apply sobre seed derivado:
- `rows_seen=8`
- `rows_with_decision=8`
- `approved_rows=8`
- `updated_rows=8`
- `validation.valid=true`

3) Replay before/after de cola (DB temporal reproducible):
- before: `actionable_queue_rows=8`
- after: `actionable_queue_rows=0`
- delta: `-8`
- detalle: `missing_designated_actor 2->0`, `institutional_designated_actor 6->0`, `missing_enforcement_evidence 1->0`

4) Test focal:
- `python3 -m unittest tests/test_scrape_liberty_delegated_person_window_boe_candidates.py tests/test_export_liberty_delegated_person_window_auto_review_decisions.py`
- resultado: `Ran 7 tests`, `OK`

5) Cobertura `candidate_person_hint` tras hardening de parser BOE:
- `candidate_rows_total=40`
- `candidate_person_hint_non_empty_total=34` (`0.85`)

## Resultado
- Slice cerrado: ya existe camino reproducible `assist -> decisiones -> apply` con reducción medible de backlog accionable.
- Gap operacional en cola: `0` filas tras replay.
- Follow-up de calidad recomendado: muestreo manual de precisión sobre decisiones auto-aprobadas.
