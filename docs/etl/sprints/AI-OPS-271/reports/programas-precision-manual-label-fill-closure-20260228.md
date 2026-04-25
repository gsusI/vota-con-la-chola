# AI-OPS-271 - Cierre de etiquetado pendiente en muestra de precision (`programas_partidos`)

## Objetivo
Cerrar el gap de `unlabeled_rows=12/40` detectado en AI-OPS-270 para restaurar auditoria completa `40/40` con contrato estricto (`min_reviewed=40`) y floor por partido (`min_party_precision>=0.85`).

## Implementacion
- Se crea paquete manual de etiquetas faltantes:
  - `docs/etl/sprints/AI-OPS-271/exports/programas_support_precision_manual_labels_fill_20260228.csv` (`12` filas, columnas `evidence_id,manual_label,manual_note`).
- Se recompone muestra etiquetada via rotacion reproducible:
  - `scripts/rotate_programas_precision_labels.py` usando dos fuentes:
    - baseline etiquetado `AI-OPS-270`
    - fill manual `AI-OPS-271`

## Validacion
1. Rotacion estricta (`--max-unlabeled 0 --strict`):
- `sample_total=40`
- `carried_forward_rows=40`
- `unlabeled_rows=0`
- `label_conflicts_total=0`
- `status=ok`

2. Auditoria de precision full-review (`--min-reviewed 40 --strict`):
- `reviewed_total=40`
- `precision=0.975` (`39 TP`, `1 FP`)
- `precision_by_required_party`:
  - `BNG=0.9`
  - `VOX=1.0`
  - `FORO Asturias=1.0`
  - `PP=1.0`
- `required_parties_min_precision=true`
- `status=ok`

3. Guardrails de pipeline no regresan:
- `quality-report --include-declared --enforce-gate`: `declared.gate.passed=true`, `review_pending=0`.
- `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`: `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-271/exports/programas_support_precision_manual_labels_fill_20260228.csv`
- `docs/etl/sprints/AI-OPS-271/exports/programas_support_precision_sample_labeled_latest.csv`
- `docs/etl/sprints/AI-OPS-271/evidence/programas_support_precision_rotate_summary_latest.json`
- `docs/etl/sprints/AI-OPS-271/evidence/programas_support_precision_audit_fullreview_latest.json`
- `docs/etl/sprints/AI-OPS-271/evidence/quality_declared_programas_enforce_latest.json`
- `docs/etl/sprints/AI-OPS-271/evidence/tracker_status_post_latest.log`

## Residual
No queda cola abierta de etiquetado para este sample (`unlabeled_rows=0`).
