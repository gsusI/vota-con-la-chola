# AI-OPS-285 — Hardening de auto-review delegado por alineación de cargo

## Objetivo
Cerrar el gap residual de AI-OPS-284: evitar auto-aprobaciones con mismatch semántico de cargo (`Dirección General` vs `Subdirección`, `Jefatura` sin jefatura real, etc.) y medir precisión únicamente sobre filas efectivamente auto-aprobadas.

## Cambios implementados
- `scripts/export_liberty_delegated_person_window_auto_review_decisions.py`
  - Nuevo criterio de alineación semántica de rol para aprobar.
  - Reglas explícitas de exclusión jerárquica (p. ej. `Dirección General` no acepta títulos de `Subdirector/Subdirección`).
  - Reglas específicas para roles recurrentes (`Jefatura`, `Delegación Especial`, `ITSS`, `autoridad gubernativa`, `unidad procedimental`).
  - Nuevos motivos de downgrade a `pending`: `auto_assist:role_alignment_failed:<reason>`.
  - Métricas nuevas en summary: `rows_missing_role_alignment_total`, `role_alignment_required`.
- `scripts/export_liberty_delegated_person_window_auto_review_qa_sample.py`
  - Añade `auto_decision` y overlaps seleccionados en CSV QA.
- `scripts/report_liberty_delegated_person_window_auto_review_qa_precision.py`
  - Añade `--decision-scope` (`approved|all`) para gate de precisión por alcance.
  - Nuevos KPIs: `rows_in_scope_total`, `rows_excluded_by_scope_total`.

## Resultados
- Auto-review (role-aligned):
  - `rows_total=8`
  - `approved_rows_total=2`
  - `pending_rows_total=6`
  - `rows_missing_role_alignment_total=6`
- QA recurrente con etiquetas manuales previas (scope `approved`):
  - `rows_in_scope_total=2`
  - `reviewed_rows_total=2`
  - `confirm_total=2`
  - `reject_total=0`
  - `observed_precision_pct=100.0`
- Apply sobre seed derivado:
  - `updated_rows=2`
  - `validation.valid=true`

## Contratos validados
- Pass estricto de precisión role-aligned:
  - `--decision-scope approved --min-reviewed-rows 2 --min-precision-pct 90 --strict` => `status=ok`.
- Fail-path de precisión:
  - `--decision-scope approved --min-reviewed-rows 2 --min-precision-pct 101 --strict` => `rc=4`.
- Fail-path de mínimo de aprobadas:
  - `--strict-min-approved-rows 3` (con `approved=2`) => `rc=4`.

## Gap residual
- El hardening elimina falsos positivos, pero deja `6` filas en `pending` que requieren revisión/captura dirigida para recuperar cobertura sin degradar precisión.

## Evidencia
- `docs/etl/sprints/AI-OPS-285/evidence/liberty_delegated_person_window_auto_review_decisions_role_aligned_latest.json`
- `docs/etl/sprints/AI-OPS-285/evidence/liberty_delegated_person_window_auto_review_qa_precision_role_aligned_latest.json`
- `docs/etl/sprints/AI-OPS-285/evidence/liberty_delegated_person_window_auto_review_qa_precision_role_aligned_fail_latest.json`
- `docs/etl/sprints/AI-OPS-285/evidence/liberty_delegated_person_window_auto_review_qa_precision_role_aligned_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-285/evidence/liberty_delegated_person_window_auto_review_apply_role_aligned_latest.json`
- `docs/etl/sprints/AI-OPS-285/evidence/liberty_delegated_ai_ops_285_summary_latest.json`
- `docs/etl/sprints/AI-OPS-285/evidence/unittest_liberty_delegated_role_alignment_latest.txt`
