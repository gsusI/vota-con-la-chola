# AI-OPS-295 — Trigger automático de QA para fallback no nominativo (delegación)

## Objetivo
Cerrar el gap operativo de la fila 720 del tracker: cuando `approved_with_non_nominative_actor_fallback_total > 0`, exigir automáticamente evidencia de QA focalizada (no depender de ejecución manual ad hoc).

## Cambios implementados
- Nuevo gate: `scripts/report_liberty_delegated_non_nominative_qa_gate.py`.
- Nuevo contrato en `justfile`:
  - `parl-report-liberty-delegated-non-nominative-qa-gate`
  - `parl-check-liberty-delegated-non-nominative-qa-gate`
  - variables `LIBERTY_DELEGATED_NON_NOMINATIVE_QA_GATE_*`.
- Cobertura unitaria: `tests/test_report_liberty_delegated_non_nominative_qa_gate.py`.

## Reglas del gate
- Si `approved_with_non_nominative_actor_fallback_total == 0`:
  - `qa_required=false` y estado `ok` sin exigir artefactos QA.
- Si `approved_with_non_nominative_actor_fallback_total > 0`:
  - exige `qa_sample_summary` y `qa_precision_report`.
  - valida filtro de muestra focalizada (`review_note_contains`).
  - valida linkage de artefactos (`auto_review.out_csv -> qa_sample.auto_review_csv -> qa_precision.qa_csv`, admitiendo variante reviewed `*_reviewed*`).
  - valida `sample_rows_total > 0`.
  - valida umbrales de QA (`min_reviewed_rows`, `min_precision_pct`).
  - en `--strict`, devuelve `rc=4` ante incumplimiento.

## Verificación
- Unit tests:
  - `python3 -m unittest tests/test_report_liberty_delegated_non_nominative_qa_gate.py tests/test_export_liberty_delegated_person_window_auto_review_qa_sample.py tests/test_report_liberty_delegated_person_window_auto_review_qa_precision.py`
  - Resultado: `Ran 11 tests ... OK`.

## Corrida real (replay AI-OPS-293/294)
1. Pass estricto:
- `status=ok`
- `qa_required=true`
- `approved_with_non_nominative_actor_fallback_total=1`
- `sample_rows_total=1`
- `reviewed_rows_total=1`
- `observed_precision_pct=100.0`
- Evidencia: `docs/etl/sprints/AI-OPS-295/evidence/liberty_delegated_non_nominative_qa_gate_latest.json`

2. Fail-path contractual:
- mismo input, `--min-precision-pct 101 --strict`
- salida `status=degraded`, `strict_fail_reasons=[qa_precision_below_min]`, `rc=4`
- Evidencia: `docs/etl/sprints/AI-OPS-295/evidence/liberty_delegated_non_nominative_qa_gate_fail_latest.json`, `docs/etl/sprints/AI-OPS-295/evidence/liberty_delegated_non_nominative_qa_gate_fail_rc_latest.txt`

## Resultado
El trigger de QA no nominativo queda automatizado y reusable en corridas nuevas: cualquier aparición de fallback no nominativo activa gate verificable con evidencia y umbrales explícitos.
