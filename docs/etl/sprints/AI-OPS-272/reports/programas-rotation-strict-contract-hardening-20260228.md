# AI-OPS-272 - Endurecimiento preventivo de rotacion de labels (`programas_partidos`)

## Objetivo
Cerrar el gap preventivo del tracker: impedir que la lane `parl-programas-precision-guardrail-rotated` pueda avanzar con `unlabeled_rows>0` por configuracion permisiva.

## Implementacion
- `justfile` endurecido con recipe dedicada:
  - Nuevo env var: `PROGRAMAS_PRECISION_ROTATE_STRICT_MAX_UNLABELED` (default `0`).
  - Nueva recipe: `parl-check-programas-support-precision-labels-rotation-strict`.
  - `parl-programas-precision-guardrail-rotated` ahora llama a la recipe strict (antes llamaba a la variant configurable con default permisivo).

## Validacion contractual
1. Pass-path strict (sample 40/40 etiquetado):
- Comando: `just parl-check-programas-support-precision-labels-rotation-strict` (overrides AI-OPS-271).
- Resultado: `sample_total=40`, `unlabeled_rows=0`, `status=ok`.

2. Fail-path strict (sample pre-cierre AI-OPS-270):
- Misma recipe strict sobre labels incompletas.
- Resultado: `unlabeled_rows=12`, `status=degraded`, `strict_fail_reasons=[max_unlabeled_exceeded]`, `rc=4`.

3. Guardrail wiring:
- Dry-run confirma llamada strict en la lane completa:
  - `just parl-check-programas-support-precision-labels-rotation-strict`

4. Guardrails globales sin regresion:
- Auditoria full-review pass (`reviewed_total=40`, `precision=0.975`, floor por partido en verde).
- `quality-report --include-declared --enforce-gate`: `declared.gate.passed=true`.
- `e2e_tracker_status`: `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-272/evidence/programas_support_precision_rotate_strict_pass_latest.json`
- `docs/etl/sprints/AI-OPS-272/evidence/programas_support_precision_rotate_strict_fail_latest.json`
- `docs/etl/sprints/AI-OPS-272/evidence/programas_support_precision_rotate_strict_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-272/evidence/just_parl_check_programas_support_precision_labels_rotation_strict_pass_latest.txt`
- `docs/etl/sprints/AI-OPS-272/evidence/just_parl_check_programas_support_precision_labels_rotation_strict_fail_latest.txt`
- `docs/etl/sprints/AI-OPS-272/evidence/just_dry_run_parl_programas_precision_guardrail_rotated_latest.txt`
- `docs/etl/sprints/AI-OPS-272/evidence/guardrail_rotated_strict_call_check_latest.txt`
- `docs/etl/sprints/AI-OPS-272/evidence/programas_support_precision_audit_fullreview_pass_latest.json`
- `docs/etl/sprints/AI-OPS-272/evidence/quality_declared_programas_enforce_latest.json`
- `docs/etl/sprints/AI-OPS-272/evidence/tracker_status_post_latest.log`
