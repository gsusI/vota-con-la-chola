# AI-OPS-288 - Hardening anti-ruido institucional en review-assist delegado

## Objetivo
Reducir falsos candidatos en `review_assist` (especialmente por coincidencias débiles de `inspección`) y mejorar cierre de `pending` sin relajar el gate semántico de cargo.

## Cambios implementados
- `scripts/export_liberty_delegated_person_window_review_assist_from_boe_candidates.py`
  - Normalización `fold` (sin tildes) para `tokenize/overlap`.
  - Expansión de acrónimos institucionales (`AEAT`, `DGT`, `ITSS`) para cálculo de `institution_token_overlap`.
  - Nuevo umbral institucional mínimo (`institution_overlap_min`) con guardrail reforzado para ITSS (`>=2`).
  - Nuevas columnas de trazabilidad en assist CSV:
    - `institution_overlap_min`
    - `institution_overlap_ok`
  - Acción recomendada explícita para baja afinidad institucional:
    - `inspect_candidate_low_institution_overlap`
  - Métrica resumida nueva:
    - `rows_below_institution_overlap_min_total`.
- `scripts/export_liberty_delegated_person_window_auto_review_decisions.py`
  - Ajuste conservador `ITSS` dirección (`itss_direction_matched`) para evitar falso negativo cuando hay dirección explícita y no hay subdirección.
- Tests:
  - `tests/test_export_liberty_delegated_person_window_review_assist_from_boe_candidates.py`
  - `tests/test_export_liberty_delegated_person_window_auto_review_decisions.py`

## Corrida reproducible
Sobre candidatos BOE dirigidos (pipeline AI-OPS-287):
1. Recalcular `review_assist` hardenizado.
2. Recalcular `auto_review` role-aligned.
3. Recalcular cola `pending_resolution`.

## Resultado
- `review_assist_targeted_summary`:
  - `assist_rows_total=85`
  - `rows_below_institution_overlap_min_total=11`
- Delta contra baseline AI-OPS-285:
  - `approved_rows_total: 2 -> 6` (`+4`)
  - `pending_rows_total: 6 -> 2` (`-4`)
  - `rows_missing_role_alignment_total: 6 -> 2` (`-4`)
- Pendientes residuales (`2`):
  - `procedural_unit_not_found`
  - `role_topic_overlap_zero`

## Cierre de item tracker
Este slice cierra el TODO de hardening anti-ruido institucional en candidatos delegados, con evidencia de contrato reproducible y mejora cuantitativa del backlog pendiente.

## Evidencia
- `docs/etl/sprints/AI-OPS-288/evidence/liberty_delegated_targeted_capture_delta_latest.json`
- `docs/etl/sprints/AI-OPS-288/evidence/liberty_delegated_targeted_capture_resolution_latest.json`
- `docs/etl/sprints/AI-OPS-288/evidence/liberty_delegated_person_window_review_assist_targeted_latest.json`
- `docs/etl/sprints/AI-OPS-288/evidence/liberty_delegated_person_window_auto_review_decisions_targeted_latest.json`
- `docs/etl/sprints/AI-OPS-288/evidence/liberty_delegated_pending_resolution_review_queue_targeted_latest.json`
- `docs/etl/sprints/AI-OPS-288/evidence/unittest_liberty_delegated_targeted_queries_latest.txt`
