# AI-OPS-260 — Cierre de rotación periódica de muestra etiquetada (`programas_partidos`)

## Objetivo
Cerrar el TODO de loop editorial periódico para que la muestra fresca del guardrail de precisión se pueda reutilizar de forma reproducible sprint a sprint, evitando volver a etiquetar desde cero.

## Implementación
- Nuevo script de rotación de etiquetas por `evidence_id`:
  - `scripts/rotate_programas_precision_labels.py`
- Nuevas lanes `just`:
  - `parl-rotate-programas-support-precision-labels`
  - `parl-check-programas-support-precision-labels-rotation`
  - `parl-programas-precision-guardrail-rotated`
- La lane `guardrail-rotated` ejecuta en un solo flujo:
  - export sample fresca
  - rotate strict (`max_unlabeled` configurable)
  - audit strict sobre sample rotada
  - `backfill-declared-stance --reconcile-no-signal`
  - recompute de posiciones
  - `quality-report --include-declared --enforce-gate`
  - `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`

## Resultado de corrida real (staging)
- Sample fresca: `40` filas (`10` por partido objetivo).
- Rotación: `carried_forward_rows=40`, `unlabeled_rows=0`, `label_conflicts_total=0`.
- Auditoría strict sobre sample rotada:
  - `reviewed_total=40`
  - `precision=0.90` (`36 TP`, `4 FP`)
  - `required_parties_covered=true`
  - `status=ok`
- Guardrail ETL post-auditoría:
  - `support=390`, `unclear=174`, `review_pending=0`
  - gate declarado `passed=true`
  - tracker enforce: `mismatches=0`, `done_zero_real=0`

## Evidencia
- `docs/etl/sprints/AI-OPS-260/evidence/programas_support_precision_sample_summary_20260228.json`
- `docs/etl/sprints/AI-OPS-260/exports/programas_support_precision_sample_latest_20260228.csv`
- `docs/etl/sprints/AI-OPS-260/evidence/programas_support_precision_rotate_summary_20260228.json`
- `docs/etl/sprints/AI-OPS-260/exports/programas_support_precision_sample_labeled_20260228.csv`
- `docs/etl/sprints/AI-OPS-260/evidence/programas_support_precision_audit_guardrail_rotated_20260228.json`
- `docs/etl/sprints/AI-OPS-260/exports/programas_support_precision_audit_guardrail_rotated_breakdown_20260228.csv`
- `docs/etl/sprints/AI-OPS-260/evidence/programas_backfill_declared_stance_guardrail_rotated_20260228.json`
- `docs/etl/sprints/AI-OPS-260/evidence/programas_backfill_declared_positions_guardrail_rotated_20260228.json`
- `docs/etl/sprints/AI-OPS-260/evidence/programas_backfill_combined_positions_guardrail_rotated_20260228.json`
- `docs/etl/sprints/AI-OPS-260/evidence/programas_declared_status_guardrail_rotated_20260228.json`
- `docs/etl/sprints/AI-OPS-260/evidence/programas_quality_declared_guardrail_rotated_20260228.json`
- `docs/etl/sprints/AI-OPS-260/evidence/tracker_status_programas_guardrail_rotated_20260228.log`
- `docs/etl/sprints/AI-OPS-260/evidence/unittest_programas_precision_rotation_20260228.txt`

## Comandos reproducibles
```bash
SNAPSHOT_DATE=2026-02-28 DB_PATH=etl/data/staging/politicos-es.db \
  PROGRAMAS_PRECISION_ROTATE_LABELS_IN=docs/etl/sprints/AI-OPS-259/exports/programas_support_precision_sample_labeled_latest.csv \
  PROGRAMAS_PRECISION_ROTATE_MAX_UNLABELED=0 \
  PROGRAMAS_PRECISION_SAMPLE_OUT=docs/etl/sprints/AI-OPS-260/exports/programas_support_precision_sample_latest_20260228.csv \
  PROGRAMAS_PRECISION_SAMPLE_SUMMARY_OUT=docs/etl/sprints/AI-OPS-260/evidence/programas_support_precision_sample_summary_20260228.json \
  PROGRAMAS_PRECISION_LABELED_OUT=docs/etl/sprints/AI-OPS-260/exports/programas_support_precision_sample_labeled_20260228.csv \
  PROGRAMAS_PRECISION_ROTATE_SUMMARY_OUT=docs/etl/sprints/AI-OPS-260/evidence/programas_support_precision_rotate_summary_20260228.json \
  PROGRAMAS_PRECISION_AUDIT_OUT=docs/etl/sprints/AI-OPS-260/evidence/programas_support_precision_audit_guardrail_rotated_20260228.json \
  PROGRAMAS_PRECISION_AUDIT_BREAKDOWN_OUT=docs/etl/sprints/AI-OPS-260/exports/programas_support_precision_audit_guardrail_rotated_breakdown_20260228.csv \
  PROGRAMAS_PRECISION_RECONCILE_OUT=docs/etl/sprints/AI-OPS-260/evidence/programas_backfill_declared_stance_guardrail_rotated_20260228.json \
  PROGRAMAS_PRECISION_DECLARED_POSITIONS_OUT=docs/etl/sprints/AI-OPS-260/evidence/programas_backfill_declared_positions_guardrail_rotated_20260228.json \
  PROGRAMAS_PRECISION_COMBINED_POSITIONS_OUT=docs/etl/sprints/AI-OPS-260/evidence/programas_backfill_combined_positions_guardrail_rotated_20260228.json \
  PROGRAMAS_PRECISION_STATUS_OUT=docs/etl/sprints/AI-OPS-260/evidence/programas_declared_status_guardrail_rotated_20260228.json \
  PROGRAMAS_PRECISION_QUALITY_OUT=docs/etl/sprints/AI-OPS-260/evidence/programas_quality_declared_guardrail_rotated_20260228.json \
  PROGRAMAS_PRECISION_TRACKER_OUT=docs/etl/sprints/AI-OPS-260/evidence/tracker_status_programas_guardrail_rotated_20260228.log \
  just parl-programas-precision-guardrail-rotated
```
