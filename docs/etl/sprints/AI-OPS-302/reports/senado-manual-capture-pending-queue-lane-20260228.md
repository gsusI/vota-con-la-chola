# AI-OPS-302 — Senado manual-capture pending queue (operational packet)

## Objetivo
Cerrar la deuda operativa entre `target progress` y ejecución manual: derivar una cola accionable de capturas pendientes con comandos ejecutables listos, sin depender de interpretación manual del CSV de progreso.

## Cambios entregados
- Nuevo script: `scripts/export_senado_manual_capture_pending_targets.py`.
  - Entrada: artefactos de progreso (`AI-OPS-301`) en JSON+CSV.
  - Salidas:
    - resumen de cola pendiente (`JSON`),
    - detalle por target (`CSV`),
    - batch ejecutable de comandos (`.sh`).
  - Reglas de pending reproducibles:
    - `unmatched_target`
    - `matched_access_denied`
    - `matched_without_domain_cookie`
    - `matched_not_usable`
  - Fallback de comando:
    - si `suggested_command` no existe en CSV de progreso, genera comando `manual_capture_playwright` desde `capture_url + suggested_label`.
- Wiring en `justfile`:
  - `parl-export-senado-manual-capture-pending-targets`
  - `parl-check-senado-manual-capture-pending-targets-empty` (strict-empty, `rc=4` con cola abierta)
- Hardening de test de ciclo AI-OPS-301:
  - `tests/test_run_senado_manual_capture_retry_cycle.py` deja de escribir defaults en `docs/etl/sprints/AI-OPS-301` (todo en tmp), evitando contaminación de evidencia real.

## Estado real (DB principal)
Corridas sobre `etl/data/staging/politicos-es.db` y progreso regenerado de `AI-OPS-301`:
- progreso base: `targets_total=8`, `matched_targets_total=6`, `usable_targets_total=0`
- cola pendiente exportada: `pending_targets_total=8`
  - `pending_unmatched_total=2`
  - `pending_matched_not_usable_total=6`
  - `pending_access_denied_total=6`
- comandos operativos: `pending_commands_total=8` (`pending_commands_fallback_total=8`)
- check strict empty: `rc=4`

## Evidencia
- `docs/etl/sprints/AI-OPS-302/evidence/senado_manual_capture_pending_targets_latest.json`
- `docs/etl/sprints/AI-OPS-302/exports/senado_manual_capture_pending_targets_latest.csv`
- `docs/etl/sprints/AI-OPS-302/exports/senado_manual_capture_pending_targets_commands_latest.sh`
- `docs/etl/sprints/AI-OPS-302/evidence/just_parl_export_senado_manual_capture_pending_targets_latest.txt`
- `docs/etl/sprints/AI-OPS-302/evidence/just_parl_check_senado_manual_capture_pending_targets_empty_latest.txt`
- `docs/etl/sprints/AI-OPS-302/evidence/just_parl_check_senado_manual_capture_pending_targets_empty_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-302/evidence/unittest_senado_manual_capture_pending_queue_lane_latest.txt`

## Estado
- Fila 829 se mantiene `PARTIAL`.
- Progreso visible bajo control del repo: la cola pendiente ya sale paquetizada y ejecutable en un `.sh` determinista.
