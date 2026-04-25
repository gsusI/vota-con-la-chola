# AI-OPS-293 - Cierre del residual no nominativo (delegación)

## Objetivo
Cerrar el último pendiente delegado (`procedural_unit_non_nominative_requires_manual`) con una regla reproducible y conservadora para unidades procedimentales sin titular nominal.

## Cambios implementados
- `scripts/export_liberty_delegated_person_window_auto_review_decisions.py`
  - Se habilita fallback **opt-in** (`--allow-non-nominative-institutional-actor-fallback`) para casos no nominativos.
  - La alineación semántica para `unidad procedimental` acepta evidencia institucional de delegación competencial (`delega el ejercicio` / `delegación de competencias`) con `institution_overlap>=3`.
  - Cuando aplica el fallback, el actor revisado se normaliza como `"<rol> (<institución>)"` y se etiqueta con `review_note` específico (`approved_non_nominative_unit_from_*`).
  - Métrica nueva en summary: `approved_with_non_nominative_actor_fallback_total`.
- `tests/test_export_liberty_delegated_person_window_auto_review_decisions.py`
  - Nueva regresión para el caso AEAT no nominativo (elige evidencia `BOE-A-2010-5072` y rellena actor institucional + fecha).

## Corrida real (AI-OPS-293)
- Re-ejecución end-to-end desde la cola residual AI-OPS-292:
  - `alternative_capture_targets -> alternative_boe_candidates -> review_assist -> auto_review(fallback on) -> pending_resolution -> apply(seed_out)`.
- Resultado:
  - `pending_rows_total: 1 -> 0`
  - `approved_rows_total: 1 -> 1` (se resuelve el único pendiente)
  - `approved_with_non_nominative_actor_fallback_total=1`
  - `pending_resolution_rows_total=0`
- Fila cerrada:
  - `link_key ... BOE-A-2004-18398`
  - `reviewed_designated_actor_label="Unidad procedimental sancionadora (AEAT)"`
  - `reviewed_enforcement_evidence_date="2010-03-27"`
  - `review_note="auto_assist:approved_non_nominative_unit_from_BOE-A-2010-5072"`
- Apply validado:
  - `rows_seen=1`, `rows_with_decision=1`, `updated_rows=1`, `validation.valid=true`.
- Fail-path contractual validado:
  - `strict_min_approved_rows=2` devuelve `rc=4`.

## Lectura operativa
- El backlog de la lane alternativa queda en `0` pendientes sin relajar controles de validación.
- La política de fallback se mantiene acotada por rol, señal semántica y overlap institucional, evitando auto-aprobar nombramientos personales no alineados con unidad procedimental.

## Evidencia
- `docs/etl/sprints/AI-OPS-293/evidence/liberty_delegated_person_window_auto_review_decisions_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-293/evidence/liberty_delegated_pending_resolution_review_queue_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-293/evidence/liberty_delegated_person_window_auto_review_apply_alternative_latest.json`
- `docs/etl/sprints/AI-OPS-293/evidence/liberty_delegated_alternative_capture_replay_delta_latest.json`
- `docs/etl/sprints/AI-OPS-293/evidence/liberty_delegated_person_window_auto_review_decisions_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-293/evidence/unittest_liberty_delegated_non_nominative_fallback_latest.txt`
- `docs/etl/sprints/AI-OPS-293/exports/liberty_delegated_person_window_auto_review_decisions_alternative_latest.csv`
