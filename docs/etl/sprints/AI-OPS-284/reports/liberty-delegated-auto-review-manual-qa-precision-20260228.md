# AI-OPS-284 — QA manual de precisión para auto-review delegado

## Objetivo
Cerrar el gap residual de AI-OPS-283 ejecutando control manual muestral (`n=8`, estratificado por institución) sobre decisiones `auto_review_decisions`, midiendo precisión observada `confirm/reject` y dejando contrato reproducible para repetir el QA.

## Cambios implementados
- Nuevo export de muestra QA estratificada:
  - `scripts/export_liberty_delegated_person_window_auto_review_qa_sample.py`
- Nuevo reporte de precisión QA con modo estricto:
  - `scripts/report_liberty_delegated_person_window_auto_review_qa_precision.py`
- Wiring en `justfile`:
  - `parl-export-liberty-delegated-person-window-auto-review-qa-sample`
  - `parl-report-liberty-delegated-person-window-auto-review-qa-precision`
  - `parl-check-liberty-delegated-person-window-auto-review-qa-precision`
- Tests añadidos:
  - `tests/test_export_liberty_delegated_person_window_auto_review_qa_sample.py`
  - `tests/test_report_liberty_delegated_person_window_auto_review_qa_precision.py`

## Ejecución
1. Export de muestra QA (`n=8`) desde auto-review + assist:
   - `just parl-export-liberty-delegated-person-window-auto-review-qa-sample`
2. Adjudicación manual (`confirm/reject`) en CSV de muestra.
3. Reporte de precisión observado:
   - `just parl-report-liberty-delegated-person-window-auto-review-qa-precision`
4. Gate estricto de contrato (min revisadas):
   - `just parl-check-liberty-delegated-person-window-auto-review-qa-precision`
5. Fail-path contractual (umbral de precisión imposible para esta muestra):
   - `python3 scripts/report_liberty_delegated_person_window_auto_review_qa_precision.py --qa-csv <qa_csv> --min-reviewed-rows 8 --min-precision-pct 50 --strict --out <fail_json>`

## Resultado
- Muestra exportada: `8/8` aprobaciones auto-review (cobertura total de fila), estratificada en 4 instituciones.
- Revisión manual completada: `reviewed_rows_total=8`.
- Decisiones manuales:
  - `confirm_total=2`
  - `reject_total=6`
  - `observed_precision_pct=25.0`
- Breakdown por institución (precisión observada):
  - `AEAT=33.3333%`
  - `DGT=0.0%`
  - `Delegaciones/Subdelegaciones del Gobierno=100.0%`
  - `Inspeccion de Trabajo y Seguridad Social=0.0%`

## Lectura operativa
- El gap de QA manual queda cerrado (muestra + adjudicación + métrica reproducible).
- La precisión observada (`25%`) no sostiene un apply plenamente automático para la mayoría de instituciones sin endurecer matching de `cargo`.
- Siguiente slice recomendado: endurecer auto-review con guardas de alineación de rol (`role_token_overlap` mínimo y reglas de exclusión para pares `Dirección General` vs `Subdirección`, etc.) antes de nuevas auto-aprobaciones masivas.

## Evidencia
- `docs/etl/sprints/AI-OPS-284/exports/liberty_delegated_person_window_auto_review_qa_sample_latest.csv`
- `docs/etl/sprints/AI-OPS-284/evidence/liberty_delegated_person_window_auto_review_qa_sample_latest.json`
- `docs/etl/sprints/AI-OPS-284/evidence/liberty_delegated_person_window_auto_review_qa_precision_latest.json`
- `docs/etl/sprints/AI-OPS-284/evidence/liberty_delegated_person_window_auto_review_qa_precision_fail_latest.json`
- `docs/etl/sprints/AI-OPS-284/evidence/liberty_delegated_person_window_auto_review_qa_precision_fail_latest.log`
- `docs/etl/sprints/AI-OPS-284/evidence/liberty_delegated_person_window_auto_review_qa_precision_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-284/evidence/unittest_liberty_delegated_auto_review_qa_latest.txt`
