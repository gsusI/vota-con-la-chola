# AI-OPS-273 - Cierre de falso positivo residual (`programas_partidos`, `evidence_id=1560538`)

## Objetivo
Cerrar el TODO residual del tracker sobre el único `false_positive` persistente en el guardrail de precisión (`evidence_id=1560538`, BNG) sin romper gates declarados ni el ratio dedupe ya cerrado en BNG europeas.

## Implementación
- Hardening semántico en `etl/parlamentario_es/declared_stance.py`:
  - Se añade bloqueador específico en `_PROGRAMA_POLICY_HARD_BLOCKER_PATTERNS` para el fragmento OCR recurrente:
  - `deben tributar aqui polo imposto de sociedades`
- Test de regresión en `tests/test_parl_declared_stance.py`:
  - nuevo caso `no_signal_bng_tax_fragment` que exige `None` en `_infer_programa_policy_support_detail`.
- Aplicación reproducible en DB real:
  - `backfill-declared-stance --source-id programas_partidos --reconcile-no-signal` para democión controlada de stances auto (`support -> unclear`) cuando tras el hardening ya no hay señal vigente.

## Validación
1. Tests:
- `python3 -m unittest tests/test_parl_declared_stance.py` (`Ran 9`, `OK`).

2. Estado del caso objetivo:
- `evidence_id=1560538` queda en `stance=unclear`, `stance_method=declared:regex_v3` (post-fix).

3. Auditoría de precisión (muestra fresca post-fix):
- Se regenera sample y se rota labels heredadas.
- Aparece 1 fila nueva sin etiqueta (`1560338`), cerrada con fill manual explícito en `AI-OPS-273`.
- Auditoría strict full-review final (`40/40`) en verde:
  - `false_positive=0`
  - `precision=1.0`
  - `precision_by_required_party={BNG:1.0, VOX:1.0, FORO:1.0, PP:1.0}`

4. Guardrails de pipeline:
- `quality-report --include-declared --enforce-gate`: `declared.gate.passed=true`, `review_pending=0`.
- Ratio BNG europeas permanece cerrado (`>=2.0`):
  - `BNG xerais=3.0`, `BNG europeas=2.0`.
- `e2e_tracker_status`: `mismatches=0`, `done_zero_real=0`.

## Delta vs AI-OPS-272
- `false_positive_total`: `1 -> 0`
- `precision`: `0.975 -> 1.0`
- `false_positive_evidence_ids`: `[1560538] -> []`

## Evidencia
- `docs/etl/sprints/AI-OPS-273/evidence/unittest_parl_declared_stance_post_residual_fp_fix_latest.txt`
- `docs/etl/sprints/AI-OPS-273/exports/programas_fp_1560538_post_fix_latest.csv`
- `docs/etl/sprints/AI-OPS-273/evidence/programas_backfill_declared_stance_reconcile_residual_fp_latest.json`
- `docs/etl/sprints/AI-OPS-273/evidence/programas_declared_status_post_residual_fp_fix_latest.json`
- `docs/etl/sprints/AI-OPS-273/evidence/programas_support_precision_sample_post_fix_summary_latest.json`
- `docs/etl/sprints/AI-OPS-273/evidence/programas_support_precision_rotate_post_fix_summary_latest.json`
- `docs/etl/sprints/AI-OPS-273/evidence/programas_support_precision_audit_post_fix_fullreview_latest.json`
- `docs/etl/sprints/AI-OPS-273/evidence/programas_residual_fp_1560538_delta_vs_ai_ops_272_latest.json`
- `docs/etl/sprints/AI-OPS-273/evidence/programas_support_unclear_unique_ratio_bng_post_residual_fp_fix_latest.json`
- `docs/etl/sprints/AI-OPS-273/evidence/quality_declared_programas_post_fix_fullreview_latest.json`
- `docs/etl/sprints/AI-OPS-273/evidence/tracker_status_post_latest.log`
- `docs/etl/sprints/AI-OPS-273/exports/programas_support_precision_manual_labels_fill_post_fp_fix_20260228.csv`
- `docs/etl/sprints/AI-OPS-273/exports/programas_support_precision_sample_post_fix_labeled_latest.csv`
