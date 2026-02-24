# AI-OPS-132 - Derechos: gates de representatividad por fuente/territorio

## Objetivo
Cerrar el gap pendiente en `Cobertura y calidad del censo de restricciones` añadiendo controles explícitos de representatividad por `fuente` y `scope territorial` (sin depender de unblock externo).

## Cambios implementados
- `scripts/report_liberty_restrictions_status.py`
  - Añade cobertura por fuente y scope:
    - `coverage_by_source`
    - `coverage_by_scope`
  - Añade métricas agregadas:
    - `sources_with_assessments_pct`
    - `scopes_with_assessments_pct`
    - `sources_total`, `sources_with_assessments_total`
    - `scopes_total`, `scopes_with_assessments_total`
  - Añade gates nuevos dentro de `checks` y `focus_gate`:
    - `source_representativity_gate`
    - `scope_representativity_gate`
  - Añade umbrales configurables:
    - `--sources-with-assessments-min-pct`
    - `--scopes-with-assessments-min-pct`
    - `--min-assessment-sources`
    - `--min-assessment-scopes`

- `scripts/report_liberty_restrictions_status_heartbeat.py`
  - Propaga al heartbeat:
    - `sources_with_assessments_pct`, `scopes_with_assessments_pct`
    - `source_representativity_gate_passed`, `scope_representativity_gate_passed`
    - totales de fuentes/scopes con cobertura
  - Endurece validación de consistencia `status=ok` vs gates de representatividad.

- `scripts/report_liberty_restrictions_status_heartbeat_window.py`
  - Añade controles strict en ventana para representatividad:
    - `--max-source-representativity-gate-failed`
    - `--max-scope-representativity-gate-failed`
  - Añade métricas/checks/reasons dedicadas:
    - `source_representativity_gate_failed_in_window`
    - `scope_representativity_gate_failed_in_window`
    - `max_source_representativity_gate_failed_ok`
    - `max_scope_representativity_gate_failed_ok`
    - `latest_source_representativity_gate_ok`
    - `latest_scope_representativity_gate_ok`
    - `max_source_representativity_gate_failed_exceeded`
    - `max_scope_representativity_gate_failed_exceeded`
    - `latest_source_representativity_gate_failed`
    - `latest_scope_representativity_gate_failed`

- `justfile`
  - Nuevos env vars y propagación en recipes de `status`/`focus gate`/`heartbeat window`:
    - `LIBERTY_RESTRICTIONS_SOURCES_WITH_ASSESSMENTS_MIN_PCT`
    - `LIBERTY_RESTRICTIONS_SCOPES_WITH_ASSESSMENTS_MIN_PCT`
    - `LIBERTY_RESTRICTIONS_MIN_ASSESSMENT_SOURCES`
    - `LIBERTY_RESTRICTIONS_MIN_ASSESSMENT_SCOPES`
    - `LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_SOURCE_REPRESENTATIVITY_GATE_FAILED`
    - `LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_SCOPE_REPRESENTATIVITY_GATE_FAILED`

- Tests
  - `tests/test_report_liberty_restrictions_status.py`
  - `tests/test_report_liberty_restrictions_status_heartbeat.py`
  - `tests/test_report_liberty_restrictions_status_heartbeat_window.py`

## Resultado de la corrida de cierre (`20260223T203640Z`)
- Status base: `ok`
  - `sources_with_assessments_pct=1.0`
  - `scopes_with_assessments_pct=1.0`
  - `source_representativity_gate=true`
  - `scope_representativity_gate=true`
- Fail-path estricto de `focus_gate` con umbrales de diversidad imposibles en seed (`min_assessment_sources=2`, `min_assessment_scopes=2`):
  - `status=degraded`
  - `source_representativity_gate=false`
  - `scope_representativity_gate=false`
  - exit code `2`
- Heartbeat base: `ok`, con gates de representatividad persistidos en `true`.
- Ventana strict base: `ok`, con `source_representativity_gate_failed_in_window=0` y `scope_representativity_gate_failed_in_window=0`.
- Fail-path sintético de ventana (latest con ambos gates `false`):
  - `status=failed`
  - `source_representativity_gate_failed_in_window=1`
  - `scope_representativity_gate_failed_in_window=1`
  - reasons incluyen:
    - `max_source_representativity_gate_failed_exceeded`
    - `max_scope_representativity_gate_failed_exceeded`
    - `latest_source_representativity_gate_failed`
    - `latest_scope_representativity_gate_failed`
  - exit code `4`

## Evidencia
- `docs/etl/sprints/AI-OPS-132/evidence/liberty_restrictions_status_20260223T203640Z.json`
- `docs/etl/sprints/AI-OPS-132/evidence/liberty_restrictions_status_representativity_fail_20260223T203640Z.json`
- `docs/etl/sprints/AI-OPS-132/evidence/just_parl_check_liberty_focus_gate_representativity_fail_rc_20260223T203640Z.txt`
- `docs/etl/sprints/AI-OPS-132/evidence/liberty_restrictions_status_heartbeat_20260223T203640Z.json`
- `docs/etl/sprints/AI-OPS-132/evidence/liberty_restrictions_status_heartbeat_window_pass_20260223T203640Z.json`
- `docs/etl/sprints/AI-OPS-132/evidence/liberty_restrictions_status_heartbeat_window_representativity_fail_20260223T203640Z.json`
- `docs/etl/sprints/AI-OPS-132/evidence/liberty_restrictions_status_heartbeat_window_representativity_fail_rc_20260223T203640Z.txt`
- `docs/etl/sprints/AI-OPS-132/evidence/unittest_liberty_representativity_contract_20260223T203640Z.txt`
- `docs/etl/sprints/AI-OPS-132/evidence/just_parl_test_liberty_restrictions_20260223T203640Z.txt`

## Comando de continuidad
- `DB_PATH=<db> just parl-liberty-restrictions-pipeline`
