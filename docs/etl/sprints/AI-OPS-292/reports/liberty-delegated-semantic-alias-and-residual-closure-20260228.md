# AI-OPS-292 - Cierre semántico parcial del replay alternativo (delegación)

## Objetivo
Reducir backlog residual del lane alternativo (`pending=2`) sin relajar gates de precisión, abordando el gap semántico detectado en AI-OPS-291.

## Cambios implementados
- `scripts/export_liberty_delegated_person_window_auto_review_decisions.py`
  - Nuevo match conservador para subdirección temática DGT:
    - rol objetivo con `subdireccion` + `sancion`
    - candidato con `Subdirector General` en `Dirección General de Tráfico`
    - alias explícito `Normativa y Recursos` / `Legislación y Recursos`.
  - Nueva razón semántica explícita para unidades procedimentales no nominativas:
    - `procedural_unit_non_nominative_requires_manual`.
- `tests/test_export_liberty_delegated_person_window_auto_review_decisions.py`
  - Regresión añadida para alias DGT (aprueba `BOE-A-2003-23115` de forma conservadora).

## Corrida real (AI-OPS-292)
- Re-ejecución completa: `alternative_capture_targets -> alternative_boe_candidates -> review_assist -> auto_review -> pending_resolution -> apply(seed_out)`.
- Delta vs AI-OPS-291:
  - `approved_rows_total: 0 -> 1`
  - `pending_rows_total: 2 -> 1`
  - `delta_pending: -1`
- Estado residual:
  - `pending_reason_counts = {auto_assist:role_alignment_failed:procedural_unit_non_nominative_requires_manual: 1}`.
- Apply validado:
  - `rows_with_decision=2`, `approved_rows=1`, `updated_rows=1`, `validation.valid=true`.
- Fail-path contractual validado:
  - `strict_min_approved_rows=2`, `rc=4`.

## Lectura operativa
- El pendiente DGT por `role_topic_overlap_zero` queda resuelto con una regla semántica acotada y trazable.
- Permanece un único residual de naturaleza institucional/no nominativa (unidad procedimental AEAT), ya clasificado explícitamente para tratamiento manual/política de evidencia.

## Evidencia
- `docs/etl/sprints/AI-OPS-292/evidence/liberty_delegated_person_window_auto_review_decisions_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-292/evidence/liberty_delegated_pending_resolution_review_queue_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-292/evidence/liberty_delegated_person_window_auto_review_apply_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-292/evidence/liberty_delegated_alternative_capture_replay_delta_latest.json`
- `docs/etl/sprints/AI-OPS-292/evidence/liberty_delegated_person_window_auto_review_decisions_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-292/evidence/liberty_delegated_alternative_boe_candidates_latest.json`
- `docs/etl/sprints/AI-OPS-292/exports/liberty_delegated_person_window_auto_review_decisions_alternative_latest.csv`
