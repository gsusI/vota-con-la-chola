# AI-OPS-278 · Loop review/apply para persona/cargo en regulacion delegada

## Objetivo
Cerrar el loop operativo encima de la cola AI-OPS-277 para convertir backlog `persona/cargo + ventana + evidencia` en un flujo reproducible de revisión y aplicación sobre seed.

## Cambios
- Nuevo exportador: `scripts/export_liberty_delegated_person_window_review_queue.py`.
  - Construye CSV revisable desde `liberty_delegated_enforcement_links`.
  - Incluye contexto actual (`current_*`) + campos de decisión (`decision`, `reviewed_*`, `review_note`).
  - Emite summary JSON y soporta `--only-actionable` + `--strict-empty-actionable`.
- Nuevo aplicador: `scripts/apply_liberty_delegated_person_window_reviews.py`.
  - Aplica filas `approved` al seed delegado.
  - Valida fechas/ventanas y ejecuta `validate_seed` sobre resultado candidato.
  - Soporta `--dry-run` y salida `--seed-out` para edición segura.
- Wiring en `justfile`:
  - `parl-export-liberty-delegated-person-window-review-queue`
  - `parl-check-liberty-delegated-person-window-review-queue-actionable-empty`
  - `parl-apply-liberty-delegated-person-window-reviews`
- Tests añadidos:
  - `tests/test_export_liberty_delegated_person_window_review_queue.py`
  - `tests/test_apply_liberty_delegated_person_window_reviews.py`

## Corrida real (staging)
DB: `etl/data/staging/politicos-es.db`.

1) Export review queue:
- `rows_total=8`
- `actionable_rows_total=8`
- `missing_seed_links_total=0`
- `by_reason={missing_designated_actor:2, institutional_designated_actor:6, missing_enforcement_evidence_date:1}`

2) Gate estricto de backlog accionable:
- `parl-check-liberty-delegated-person-window-review-queue-actionable-empty`
- resultado esperado: `rc=4` (hay trabajo pendiente)

3) Apply dry-run (sin mutar seed canonical):
- `rows_seen=8`
- `rows_with_decision=0`
- `updated_rows=0`
- `validation.valid=true`

4) Tests:
- `python3 -m unittest tests/test_export_liberty_delegated_person_window_review_queue.py tests/test_apply_liberty_delegated_person_window_reviews.py`
- resultado: `Ran 2 tests`, `OK`

## Resultado
- Slice cerrado: la cola delegada ya tiene ciclo completo `queue -> review CSV -> apply` con contrato estricto reproducible.
- El lane principal de regulación delegada permanece `PARTIAL` hasta aplicar decisiones no vacías y sustituir placeholders institucionales por evidencia persona/cargo/fecha en seed.
