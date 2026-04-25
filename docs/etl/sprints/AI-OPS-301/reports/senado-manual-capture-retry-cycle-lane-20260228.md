# AI-OPS-301 — Senado manual-capture retry cycle (gate + execute)

## Objetivo
Cerrar deuda operativa de la fila 829 consolidando en un único ciclo reproducible:
1) gate de progreso de capturas manuales,
2) selección de cookie utilizable más reciente,
3) ejecución condicional de `backfill-initiative-documents`.

## Cambios entregados
- Nuevo runner: `scripts/run_senado_manual_capture_retry_cycle.py`.
  - Reusa el gate de progreso (`report_senado_manual_capture_target_progress.py`).
  - Evalúa inventario de capturas (`usable_capture` + existencia de cookie file).
  - Ejecuta `backfill-initiative-documents` solo si la palanca está lista.
  - Emite artefacto único de ciclo con checks, razones strict y comando efectivo.
- Wiring `justfile`:
  - `parl-run-senado-manual-capture-retry-cycle`
  - `parl-check-senado-manual-capture-retry-cycle`
- Cobertura de tests:
  - `tests/test_run_senado_manual_capture_retry_cycle.py`.

## Resultado en DB real (etl/data/staging/politicos-es.db)
- `status=degraded` (esperado por bloqueo externo actual).
- Gate de progreso:
  - `targets_total=8`
  - `matched_targets_total=6` (`coverage_pct=0.75`)
  - `usable_targets_total=0` (`usable_coverage_pct=0.0`)
- Inventario de capturas:
  - `capture_files_total=2`
  - `usable_capture_files_total=0`
  - `usable_with_cookie_files_total=0`
- Retry de descarga:
  - `backfill.attempted=false`
  - `skip_reason=capture_gate_not_ready`
- Check estricto:
  - `rc=4`

## Evidencia
- Ciclo real: `docs/etl/sprints/AI-OPS-301/evidence/senado_manual_capture_retry_cycle_latest.json`
- Gate de progreso (materializado por ciclo): `docs/etl/sprints/AI-OPS-301/evidence/senado_manual_capture_target_progress_latest.json`
- CSV de progreso por target: `docs/etl/sprints/AI-OPS-301/exports/senado_manual_capture_target_progress_latest.csv`
- Run command: `docs/etl/sprints/AI-OPS-301/evidence/just_parl_run_senado_manual_capture_retry_cycle_latest.txt`
- Strict check + RC: `docs/etl/sprints/AI-OPS-301/evidence/just_parl_check_senado_manual_capture_retry_cycle_latest.txt`, `docs/etl/sprints/AI-OPS-301/evidence/just_parl_check_senado_manual_capture_retry_cycle_rc_latest.txt`
- Tests lane: `docs/etl/sprints/AI-OPS-301/evidence/unittest_senado_manual_capture_retry_cycle_lane_latest.txt`
- Paridad tracker: `docs/etl/sprints/AI-OPS-301/evidence/tracker_status_latest.log`

## Estado
- Fila 829 se mantiene `PARTIAL`: deuda controlable cerrada (gate+runner), bloqueo externo persiste (sin captura usable).
