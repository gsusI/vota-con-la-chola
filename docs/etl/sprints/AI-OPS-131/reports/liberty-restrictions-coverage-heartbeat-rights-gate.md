# AI-OPS-131 — Derechos/Cobertura: heartbeat-window con gate `rights_with_data`

Fecha: 2026-02-23 (UTC)

## Objetivo
Alinear la observabilidad periódica de cobertura (`heartbeat` + `window`) con el nuevo gate de mapa por derecho (`rights_with_data`) para detectar regresiones automáticamente en la rutina operativa y en CI.

## Cambios aplicados
- `scripts/report_liberty_restrictions_status_heartbeat.py`
  - añade persistencia de:
    - `right_categories_with_data_pct`
    - `rights_with_data_gate_passed`
  - endurece validación con mismatch:
    - `rights_with_data_gate_status_mismatch` cuando `status=ok` pero el gate va en `false`.
- `scripts/report_liberty_restrictions_status_heartbeat_window.py`
  - añade umbral nuevo `--max-rights-with-data-gate-failed`.
  - añade métricas y checks:
    - `rights_with_data_gate_failed_in_window`
    - `checks.max_rights_with_data_gate_failed_ok`
    - `checks.latest_rights_with_data_gate_ok`
  - añade razones strict:
    - `max_rights_with_data_gate_failed_exceeded`
    - `latest_rights_with_data_gate_failed`
  - compatibilidad retroactiva:
    - para entradas antiguas sin `rights_with_data_gate_passed`, la ventana no cuenta fallo histórico por ausencia de campo.
- `justfile`
  - nueva variable: `LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_RIGHTS_WITH_DATA_GATE_FAILED` (default `0`).
  - `parl-check-liberty-restrictions-status-heartbeat-window` propaga el nuevo umbral.
- Tests
  - `tests/test_report_liberty_restrictions_status_heartbeat.py` actualizado para cubrir el campo nuevo.
  - `tests/test_report_liberty_restrictions_status_heartbeat_window.py` actualizado + caso nuevo de fail-path por `rights_with_data`.

## Ejecución reproducible
Base temporal usada:
- DB: `tmp/aiops131/liberty_heartbeat_20260223T202651Z.db`
- Heartbeat path: `tmp/aiops131/liberty_restrictions_status_heartbeat_20260223T202651Z.jsonl`

Pasos ejecutados:
1. Import de semillas (`sanction_norms`, `liberty_restrictions`).
2. Reporte de status en `rights_with_data_min=1.0`.
3. Heartbeat append-only desde status.
4. Window strict pass-path con umbral `max_rights_with_data_gate_failed=0`.
5. Window strict fail-path sintético (última entrada con `rights_with_data_gate_passed=false`).
6. Test suite focal + `just parl-test-liberty-restrictions`.

## Resultados
- Import restricciones: `assessments_inserted=11`.
- Status base: `status=ok`, `right_categories_with_data_pct=1.0`, `rights_with_data_gate=true`.
- Heartbeat: `status=ok`, `rights_with_data_gate_passed=true`.
- Window pass-path: `status=ok`, `rights_with_data_gate_failed_in_window=0`.
- Window fail-path: `status=failed`, `rights_with_data_gate_failed_in_window=1`, razones strict:
  - `max_rights_with_data_gate_failed_exceeded`
  - `latest_rights_with_data_gate_failed`
  - retorno estricto: `exit=4`.
- Test suite:
  - focal heartbeat: `Ran 7 tests ... OK`
  - suite completa derechos: `Ran 52 tests ... OK (skipped=1)`

## Evidencia
- `docs/etl/sprints/AI-OPS-131/evidence/sanction_norms_seed_import_20260223T202651Z.json`
- `docs/etl/sprints/AI-OPS-131/evidence/liberty_restrictions_import_20260223T202651Z.json`
- `docs/etl/sprints/AI-OPS-131/evidence/liberty_restrictions_status_20260223T202651Z.json`
- `docs/etl/sprints/AI-OPS-131/evidence/liberty_restrictions_status_heartbeat_20260223T202651Z.json`
- `docs/etl/sprints/AI-OPS-131/evidence/liberty_restrictions_status_heartbeat_window_pass_20260223T202651Z.json`
- `docs/etl/sprints/AI-OPS-131/evidence/liberty_restrictions_status_heartbeat_window_fail_20260223T202651Z.json`
- `docs/etl/sprints/AI-OPS-131/evidence/liberty_restrictions_status_heartbeat_window_fail_rc_20260223T202651Z.txt`
- `docs/etl/sprints/AI-OPS-131/evidence/unittest_liberty_restrictions_heartbeat_contract_20260223T202651Z.txt`
- `docs/etl/sprints/AI-OPS-131/evidence/just_parl_test_liberty_restrictions_20260223T202651Z.txt`
- `docs/etl/sprints/AI-OPS-131/exports/liberty_restrictions_status_heartbeat_fail_input_latest.jsonl`

## Estado
DONE (el contrato de cobertura periódica ya detecta regressions de `rights_with_data` en tiempo de operación).
