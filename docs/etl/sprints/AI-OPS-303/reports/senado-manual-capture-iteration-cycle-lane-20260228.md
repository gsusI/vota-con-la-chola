# AI-OPS-303 — Senado manual capture iteration cycle (2026-02-28)

## Objetivo
Cerrar la deuda de orquestación entre el retry condicional (AI-OPS-301) y la cola de pendientes (AI-OPS-302) en una sola ejecución reproducible, con delta de pendientes entre iteraciones.

## Entregable
- Nuevo orquestador `scripts/run_senado_manual_capture_iteration_cycle.py`.
- Integración `just`:
  - `parl-run-senado-manual-capture-iteration-cycle`
  - `parl-check-senado-manual-capture-iteration-cycle`
- Hardening de ejecución directa del script (fallback de imports `scripts.*` cuando se invoca como `python3 scripts/...`).

## Resultado real (DB principal)
Comandos ejecutados sobre `etl/data/staging/politicos-es.db`:
- `just parl-run-senado-manual-capture-iteration-cycle`
- `just parl-check-senado-manual-capture-iteration-cycle`

Estado combinado:
- `status=degraded`
- `previous_pending_total=8`
- `current_pending_total=8`
- `pending_reduction_total=0`
- `retry_rc=0`, `pending_rc=0`

Gates relevantes:
- `retry_report_ok=false`
- `pending_report_ok=true`
- `pending_queue_empty=false`
- `backfill_attempted=false`
- `backfill_ok=false`
- strict check: `rc=4`

Desglose operativo observado:
- progreso de captura: `targets_total=8`, `matched_targets_total=6`, `unmatched_targets_total=2`, `usable_targets_total=0`
- inventario de capturas: `capture_files_total=2`, `usable_capture_files_total=0`
- cola pendiente: `pending_targets_total=8` (`unmatched_target=2`, `matched_access_denied=6`)

## Conclusión
La lane AI-OPS-303 queda cerrada como slice controlable: el ciclo completo `retry + pending + delta` ya es reproducible y auditable en un comando, con evidencia de estado y fail estricto cuando la cola sigue abierta.

Bloqueo externo vigente: persiste ausencia de captura usable (WAF/challenge), por lo que no se dispara `backfill-initiative-documents`.

## Evidencia
- `docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_iteration_cycle_latest.json`
- `docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_retry_cycle_latest.json`
- `docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_target_progress_latest.json`
- `docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_pending_targets_latest.json`
- `docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_target_progress_latest.csv`
- `docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_pending_targets_latest.csv`
- `docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_pending_targets_commands_latest.sh`
- `docs/etl/sprints/AI-OPS-303/evidence/just_parl_run_senado_manual_capture_iteration_cycle_latest.txt`
- `docs/etl/sprints/AI-OPS-303/evidence/just_parl_check_senado_manual_capture_iteration_cycle_latest.txt`
- `docs/etl/sprints/AI-OPS-303/evidence/just_parl_check_senado_manual_capture_iteration_cycle_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-303/evidence/unittest_senado_manual_capture_iteration_lane_latest.txt`
- `docs/etl/sprints/AI-OPS-303/evidence/tracker_status_latest.log`

## Siguiente comando
`bash docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_pending_targets_commands_latest.sh && just parl-run-senado-manual-capture-iteration-cycle && just parl-check-senado-manual-capture-iteration-cycle`
