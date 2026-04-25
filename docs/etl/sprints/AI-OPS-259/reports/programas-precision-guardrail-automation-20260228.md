# AI-OPS-259 — Guardrail continuo de precisión + reconciliación (`programas_partidos`)

## Objetivo
Cerrar la lane TODO de guardrail continuo para cambios semánticos en `declared_stance`, con ejecución reproducible en un único flujo operativo.

## Implementación
- Nuevo export determinista de muestra estratificada por partido:
  - `scripts/export_programas_support_precision_sample.py`
- Nuevo reporte/gate de precisión sobre muestra etiquetada (`manual_label=true_positive|false_positive`):
  - `scripts/report_programas_support_precision_audit.py`
- Nuevas lanes `just`:
  - `parl-export-programas-support-precision-sample`
  - `parl-report-programas-support-precision-audit`
  - `parl-check-programas-support-precision-audit` (strict)
  - `parl-programas-precision-guardrail` (check precision + reconcile + recompute + quality/tracker enforce)

## Resultado de corrida real (staging)
- `just parl-export-programas-support-precision-sample`:
  - muestra fresca `40` filas (`10` por partido objetivo `BNG/VOX/FORO Asturias/PP`), sin partidos faltantes.
- `just parl-check-programas-support-precision-audit`:
  - muestra etiquetada (`AI-OPS-258`) en verde: `reviewed=36`, `precision=0.9722`, umbral `0.90`, `status=ok`.
- `just parl-programas-precision-guardrail`:
  - reconciliación ejecutada con `--reconcile-no-signal` (idempotente en esta corrida: `updated=0`, `reconciled_no_signal=0`).
  - estado declarado final estable: `support=390`, `unclear=174`, `review_pending=0`.
  - gate declarado: `passed=true`.
  - tracker enforce: `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-259/evidence/programas_support_precision_sample_summary_latest.json`
- `docs/etl/sprints/AI-OPS-259/exports/programas_support_precision_sample_latest.csv`
- `docs/etl/sprints/AI-OPS-259/evidence/programas_support_precision_audit_latest.json`
- `docs/etl/sprints/AI-OPS-259/exports/programas_support_precision_audit_breakdown_latest.csv`
- `docs/etl/sprints/AI-OPS-259/evidence/programas_backfill_declared_stance_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-259/evidence/programas_backfill_declared_positions_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-259/evidence/programas_backfill_combined_positions_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-259/evidence/programas_declared_status_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-259/evidence/programas_quality_declared_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-259/evidence/tracker_status_programas_guardrail_latest.log`
- tests: `tests/test_export_programas_support_precision_sample.py`, `tests/test_report_programas_support_precision_audit.py`

## Comandos reproducibles
```bash
SNAPSHOT_DATE=2026-02-28 DB_PATH=etl/data/staging/politicos-es.db just parl-export-programas-support-precision-sample
SNAPSHOT_DATE=2026-02-28 DB_PATH=etl/data/staging/politicos-es.db just parl-check-programas-support-precision-audit
SNAPSHOT_DATE=2026-02-28 DB_PATH=etl/data/staging/politicos-es.db just parl-programas-precision-guardrail
```
