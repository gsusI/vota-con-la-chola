# AI-OPS-134 - Derechos: gate de evidencia primaria en accountability

## Objetivo
Convertir la cobertura de accountability en una señal auditable: no basta con que exista un edge de responsabilidad, también debe poder rastrearse con evidencia primaria fechada (`source_url`, `evidence_date`, `evidence_quote`).

## Cambios implementados
- `scripts/report_liberty_restrictions_status.py`
  - Añade métricas globales:
    - `accountability_edges_total`
    - `accountability_edges_with_primary_evidence_total`
    - `accountability_edges_with_primary_evidence_pct`
  - Añade cobertura por fuente/scope de evidencia primaria:
    - `fragments_with_accountability_primary_evidence_total/pct`
  - Añade gate nuevo en `focus_gate`:
    - `accountability_primary_evidence_gate`
  - Añade umbrales configurables:
    - `--accountability-primary-evidence-min-pct`
    - `--min-accountability-primary-evidence-edges`

- `scripts/report_liberty_restrictions_status_heartbeat.py`
  - Propaga al heartbeat:
    - `accountability_edges_total`
    - `accountability_edges_with_primary_evidence_total`
    - `accountability_edges_with_primary_evidence_pct`
    - `accountability_primary_evidence_gate_passed`
  - Endurece validación strict para inconsistencias `status=ok` con gate `false`.

- `scripts/report_liberty_restrictions_status_heartbeat_window.py`
  - Añade umbral strict de ventana:
    - `--max-accountability-primary-evidence-gate-failed`
  - Añade métricas/checks/reasons:
    - `accountability_primary_evidence_gate_failed_in_window`
    - `max_accountability_primary_evidence_gate_failed_ok`
    - `latest_accountability_primary_evidence_gate_ok`
    - `max_accountability_primary_evidence_gate_failed_exceeded`
    - `latest_accountability_primary_evidence_gate_failed`

- `justfile`
  - Nuevos env vars para status/focus/window:
    - `LIBERTY_RESTRICTIONS_ACCOUNTABILITY_PRIMARY_EVIDENCE_MIN_PCT`
    - `LIBERTY_RESTRICTIONS_MIN_ACCOUNTABILITY_PRIMARY_EVIDENCE_EDGES`
    - `LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_ACCOUNTABILITY_PRIMARY_EVIDENCE_GATE_FAILED`

- Tests
  - `tests/test_report_liberty_restrictions_status.py`
  - `tests/test_report_liberty_restrictions_status_heartbeat.py`
  - `tests/test_report_liberty_restrictions_status_heartbeat_window.py`

## Resultado de la corrida de cierre (`20260223T205756Z`)
- Import semilla: `status=ok`, `assessments_total=11`.
- Status base: `ok`
  - `accountability_edges_total=15`
  - `accountability_edges_with_primary_evidence_total=0`
  - `accountability_edges_with_primary_evidence_pct=0.0`
  - `accountability_primary_evidence_gate=true` (umbral default `0.0`, modo observabilidad)
- Fail-path estricto de `focus_gate`:
  - `accountability_primary_evidence_min_pct=0.1`
  - `min_accountability_primary_evidence_edges=1`
  - resultado: `status=degraded`, `accountability_primary_evidence_gate=false`, exit code `2`
- Heartbeat base: `ok`, gate de evidencia primaria persistido.
- Ventana strict base: `ok`.
- Fail-path sintético de ventana (latest con `focus_gate=true` y `accountability_primary_evidence_gate_passed=false`):
  - `status=failed`
  - `accountability_primary_evidence_gate_failed_in_window=1`
  - reasons:
    - `max_accountability_primary_evidence_gate_failed_exceeded`
    - `latest_accountability_primary_evidence_gate_failed`
  - exit code `4`

## Evidencia
- `docs/etl/sprints/AI-OPS-134/evidence/liberty_restrictions_import_20260223T205756Z.json`
- `docs/etl/sprints/AI-OPS-134/evidence/liberty_restrictions_status_20260223T205756Z.json`
- `docs/etl/sprints/AI-OPS-134/evidence/liberty_restrictions_status_accountability_primary_evidence_fail_20260223T205756Z.json`
- `docs/etl/sprints/AI-OPS-134/evidence/just_parl_check_liberty_focus_gate_accountability_primary_evidence_fail_rc_20260223T205756Z.txt`
- `docs/etl/sprints/AI-OPS-134/evidence/liberty_restrictions_status_heartbeat_20260223T205756Z.json`
- `docs/etl/sprints/AI-OPS-134/evidence/liberty_restrictions_status_heartbeat_window_pass_20260223T205756Z.json`
- `docs/etl/sprints/AI-OPS-134/evidence/liberty_restrictions_status_heartbeat_window_accountability_primary_evidence_fail_20260223T205756Z.json`
- `docs/etl/sprints/AI-OPS-134/evidence/just_parl_check_liberty_restrictions_status_heartbeat_window_accountability_primary_evidence_fail_rc_20260223T205756Z.txt`
- `docs/etl/sprints/AI-OPS-134/evidence/unittest_liberty_accountability_primary_evidence_contract_20260223T205756Z.txt`
- `docs/etl/sprints/AI-OPS-134/evidence/just_parl_test_liberty_restrictions_20260223T205756Z.txt`

## Comando de continuidad
- `DB_PATH=<db> just parl-liberty-restrictions-pipeline`
