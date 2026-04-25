# AI-OPS-294 - QA manual del fallback no nominativo (delegación)

## Objetivo
Cerrar el guardrail pendiente para el fallback no nominativo (`approved_non_nominative_unit`) con muestreo focalizado y verificación manual reproducible.

## Cambios implementados
- `scripts/export_liberty_delegated_person_window_auto_review_qa_sample.py`
  - Nuevo filtro opcional `--review-note-contains` para extraer muestras QA focalizadas por patrón de `review_note`.
  - Hardening de trazabilidad BOE en QA sampler: `_parse_boe_id_from_review_note(...)` ahora reconoce tanto `approved_from_*` como `approved_non_nominative_unit_from_*`, evitando seleccionar un candidato distinto al realmente aprobado.
- `tests/test_export_liberty_delegated_person_window_auto_review_qa_sample.py`
  - Nueva regresión para filtro por `review_note` y mapeo correcto al `BOE-A-*` referenciado en la nota de aprobación no nominativa.

## Corrida real (AI-OPS-294)
- Input:
  - `auto_review`: `docs/etl/sprints/AI-OPS-293/exports/liberty_delegated_person_window_auto_review_decisions_alternative_latest.csv`
  - `review_assist`: `docs/etl/sprints/AI-OPS-293/exports/liberty_delegated_person_window_review_assist_alternative_latest.csv`
- Muestreo focalizado:
  - `--review-note-contains approved_non_nominative_unit`
  - `rows_considered_total=1`, `sample_rows_total=1`, `sample_covers_all_rows=true`
- Adjudicación manual:
  - `qa_decision=confirm` en `1/1` filas
- Reporte de precisión (estricto):
  - `decision_scope=approved`
  - `reviewed_rows_total=1`
  - `confirm_total=1`, `reject_total=0`
  - `observed_precision_pct=100.0`
  - `strict_fail_reasons=[]`
- Fail-path contractual validado:
  - `min_precision_pct=101` con `--strict` devuelve `rc=4`.

## Lectura operativa
- El fallback no nominativo queda con control manual explícito y reproducible.
- La muestra QA referencia correctamente el BOE usado para aprobar (`BOE-A-2010-5072`), manteniendo coherencia entre decisión automática y evidencia revisada.

## Evidencia
- `docs/etl/sprints/AI-OPS-294/evidence/liberty_delegated_non_nominative_auto_review_qa_sample_latest.json`
- `docs/etl/sprints/AI-OPS-294/evidence/liberty_delegated_non_nominative_auto_review_qa_precision_latest.json`
- `docs/etl/sprints/AI-OPS-294/evidence/liberty_delegated_non_nominative_auto_review_qa_precision_fail_latest.json`
- `docs/etl/sprints/AI-OPS-294/evidence/liberty_delegated_non_nominative_auto_review_qa_precision_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-294/evidence/liberty_delegated_non_nominative_auto_review_qa_summary_latest.json`
- `docs/etl/sprints/AI-OPS-294/evidence/unittest_liberty_delegated_non_nominative_auto_review_qa_latest.txt`
- `docs/etl/sprints/AI-OPS-294/exports/liberty_delegated_non_nominative_auto_review_qa_sample_latest.csv`
- `docs/etl/sprints/AI-OPS-294/exports/liberty_delegated_non_nominative_auto_review_qa_sample_reviewed_latest.csv`
