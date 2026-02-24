# AI-OPS-133 - Derechos: gates de doble cobertura fuente/scope (IRLC + accountability)

## Objetivo
Endurecer `Cobertura y calidad del censo de restricciones` con un control adicional de representatividad: no solo medir que haya assessments por fuente/scope, sino exigir doble cobertura (`IRLC` + `accountability`) por fuente y por ámbito territorial.

## Cambios implementados
- `scripts/report_liberty_restrictions_status.py`
  - Extiende `coverage_by_source` y `coverage_by_scope` con:
    - `fragments_with_accountability_total/pct`
    - `fragments_with_dual_coverage_total/pct`
  - Añade métricas agregadas:
    - `sources_with_dual_coverage_pct`
    - `scopes_with_dual_coverage_pct`
    - `sources_with_dual_coverage_total`
    - `scopes_with_dual_coverage_total`
  - Añade gates nuevos en `focus_gate`:
    - `source_dual_coverage_gate`
    - `scope_dual_coverage_gate`
  - Añade umbrales configurables:
    - `--sources-with-dual-coverage-min-pct`
    - `--scopes-with-dual-coverage-min-pct`
    - `--min-dual-coverage-sources`
    - `--min-dual-coverage-scopes`

- `scripts/report_liberty_restrictions_status_heartbeat.py`
  - Propaga al heartbeat:
    - `sources_with_dual_coverage_pct`, `scopes_with_dual_coverage_pct`
    - `source_dual_coverage_gate_passed`, `scope_dual_coverage_gate_passed`
    - `sources_with_dual_coverage_total`, `scopes_with_dual_coverage_total`
  - Endurece validación strict para detectar inconsistencias `status=ok` con gates de doble cobertura en `false`.

- `scripts/report_liberty_restrictions_status_heartbeat_window.py`
  - Añade umbrales strict de ventana:
    - `--max-source-dual-coverage-gate-failed`
    - `--max-scope-dual-coverage-gate-failed`
  - Añade checks/reasons dedicados:
    - `max_source_dual_coverage_gate_failed_ok`
    - `max_scope_dual_coverage_gate_failed_ok`
    - `latest_source_dual_coverage_gate_ok`
    - `latest_scope_dual_coverage_gate_ok`
    - `max_source_dual_coverage_gate_failed_exceeded`
    - `max_scope_dual_coverage_gate_failed_exceeded`
    - `latest_source_dual_coverage_gate_failed`
    - `latest_scope_dual_coverage_gate_failed`

- `justfile`
  - Nuevos env vars y propagación en recipes `status`, `focus gate` y `heartbeat window`:
    - `LIBERTY_RESTRICTIONS_SOURCES_WITH_DUAL_COVERAGE_MIN_PCT`
    - `LIBERTY_RESTRICTIONS_SCOPES_WITH_DUAL_COVERAGE_MIN_PCT`
    - `LIBERTY_RESTRICTIONS_MIN_DUAL_COVERAGE_SOURCES`
    - `LIBERTY_RESTRICTIONS_MIN_DUAL_COVERAGE_SCOPES`
    - `LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_SOURCE_DUAL_COVERAGE_GATE_FAILED`
    - `LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_SCOPE_DUAL_COVERAGE_GATE_FAILED`

- Tests
  - `tests/test_report_liberty_restrictions_status.py`
  - `tests/test_report_liberty_restrictions_status_heartbeat.py`
  - `tests/test_report_liberty_restrictions_status_heartbeat_window.py`

## Resultado de la corrida de cierre (`20260223T204632Z`)
- Import semilla: `status=ok`, `assessments_updated=11`, `assessments_total=11`.
- Status base: `ok`
  - `sources_with_dual_coverage_pct=1.0`
  - `scopes_with_dual_coverage_pct=1.0`
  - `source_dual_coverage_gate=true`
  - `scope_dual_coverage_gate=true`
- Fail-path estricto de `focus_gate` con umbrales imposibles en seed (`min_dual_coverage_sources=2`, `min_dual_coverage_scopes=2`):
  - `status=degraded`
  - `source_dual_coverage_gate=false`
  - `scope_dual_coverage_gate=false`
  - exit code `2`
- Heartbeat base: `ok`, con gates de doble cobertura persistidos en `true`.
- Ventana strict base: `ok`, con `source_dual_coverage_gate_failed_in_window=0` y `scope_dual_coverage_gate_failed_in_window=0`.
- Fail-path sintético de ventana (latest con ambos gates de doble cobertura en `false` y `focus_gate=true`):
  - `status=failed`
  - `source_dual_coverage_gate_failed_in_window=1`
  - `scope_dual_coverage_gate_failed_in_window=1`
  - reasons incluyen:
    - `max_source_dual_coverage_gate_failed_exceeded`
    - `max_scope_dual_coverage_gate_failed_exceeded`
    - `latest_source_dual_coverage_gate_failed`
    - `latest_scope_dual_coverage_gate_failed`
  - exit code `4`

## Evidencia
- `docs/etl/sprints/AI-OPS-133/evidence/liberty_restrictions_import_20260223T204632Z.json`
- `docs/etl/sprints/AI-OPS-133/evidence/liberty_restrictions_status_20260223T204632Z.json`
- `docs/etl/sprints/AI-OPS-133/evidence/liberty_restrictions_status_dual_coverage_fail_20260223T204632Z.json`
- `docs/etl/sprints/AI-OPS-133/evidence/just_parl_check_liberty_focus_gate_dual_coverage_fail_rc_20260223T204632Z.txt`
- `docs/etl/sprints/AI-OPS-133/evidence/liberty_restrictions_status_heartbeat_20260223T204632Z.json`
- `docs/etl/sprints/AI-OPS-133/evidence/liberty_restrictions_status_heartbeat_window_pass_20260223T204632Z.json`
- `docs/etl/sprints/AI-OPS-133/evidence/liberty_restrictions_status_heartbeat_window_dual_coverage_fail_20260223T204632Z.json`
- `docs/etl/sprints/AI-OPS-133/evidence/just_parl_check_liberty_restrictions_status_heartbeat_window_dual_coverage_fail_rc_20260223T204632Z.txt`
- `docs/etl/sprints/AI-OPS-133/evidence/unittest_liberty_dual_coverage_contract_20260223T204632Z.txt`
- `docs/etl/sprints/AI-OPS-133/evidence/just_parl_test_liberty_restrictions_20260223T204632Z.txt`

## Comando de continuidad
- `DB_PATH=<db> just parl-liberty-restrictions-pipeline`
