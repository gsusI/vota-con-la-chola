# AI-OPS-286 — Resolución manual de pendientes tras hardening de cargo

## Objetivo
Cerrar el TODO operativo de pendientes (`pending=6`) posterior al hardening AI-OPS-285, dejando decisión explícita por fila y una cola estructurada de captura dirigida sin reintroducir falsos positivos.

## Cambios implementados
- Nuevo exportador de cola de resolución focalizada:
  - `scripts/export_liberty_delegated_pending_resolution_review_queue.py`
  - Toma `auto_review` role-aligned + `review_assist` (deep) y genera una cola por fila pendiente con:
    - `pending_reason`
    - `top_candidates_json` (shortlist estructurada)
    - `capture_query_primary/secondary`
    - columnas compatibles con `apply_liberty_delegated_person_window_reviews.py`
- Test del exportador:
  - `tests/test_export_liberty_delegated_pending_resolution_review_queue.py`
- Wiring en `justfile`:
  - `parl-export-liberty-delegated-pending-resolution-review-queue`

## Ejecución
1. Deep scrape y assist (AI-OPS-285) para ampliar base de candidatos.
2. Export de cola de pendientes:
   - `pending_rows_total=6`
   - `links_with_candidates_total=6`
3. Adjudicación manual de cola (`decision` por fila):
   - `pending=6`, `approved=0`
   - nota uniforme: `manual_review_top5_no_role_aligned_candidate`
4. Apply del CSV adjudicado sobre seed derivado AI-OPS-285.

## Resultados
- Se cierra el loop de revisión/cierre para los 6 pendientes con decisión explícita por fila.
- No hay cambios automáticos nuevos al seed en esta pasada (`updated_rows=0`) por diseño conservador.
- Validación del seed post-apply: `valid=true`.

## Evidencia
- `docs/etl/sprints/AI-OPS-286/exports/liberty_delegated_pending_resolution_review_queue_latest.csv`
- `docs/etl/sprints/AI-OPS-286/exports/liberty_delegated_pending_resolution_reviews_latest.csv`
- `docs/etl/sprints/AI-OPS-286/evidence/liberty_delegated_pending_resolution_review_queue_latest.json`
- `docs/etl/sprints/AI-OPS-286/evidence/liberty_delegated_pending_resolution_apply_latest.json`
- `docs/etl/sprints/AI-OPS-286/evidence/liberty_delegated_pending_resolution_summary_latest.json`
- `docs/etl/sprints/AI-OPS-286/evidence/unittest_liberty_delegated_pending_resolution_latest.txt`

## Nota operativa
- El estado `pending` ya no representa backlog sin tratar: representa backlog revisado y explicitado.
- Siguiente palanca real para convertir estos `pending` en `approved` es captura/ingesta de evidencia oficial adicional por cargo exacto (no hay match semántico suficiente en shortlist BOE actual).
