# AI-OPS-130 — Derechos/Mapa: cobertura completa por derecho + gate operativo

Fecha: 2026-02-23 (UTC)

## Objetivo
Cerrar el gap operativo del mapa de restricciones por derecho (`privacidad`, `acceso_servicios`, `propiedad_uso`) y endurecer el gate para evitar regresión de cobertura por categorías.

## Cambios aplicados
- Semilla `liberty_restrictions_seed_v1` ampliada con 3 evaluaciones IRLC nuevas para cubrir categorías antes vacías:
  - `right:privacidad`
  - `right:acceso_servicios`
  - `right:propiedad_uso`
- `scripts/report_liberty_restrictions_status.py` endurecido con:
  - métrica `right_categories_with_data_total`
  - métrica `coverage.right_categories_with_data_pct`
  - check `checks.rights_with_data_gate`
  - umbral nuevo `--rights-with-data-min` (incluido en `focus_gate.thresholds`)
  - `focus_gate.passed` ahora exige también `rights_with_data_gate`
- `justfile` actualizado para propagar el umbral nuevo en:
  - `parl-report-liberty-restrictions-status`
  - `parl-check-liberty-focus-gate`
  - var: `LIBERTY_RESTRICTIONS_RIGHTS_WITH_DATA_MIN` (default `1.0`)
- Tests actualizados:
  - `tests/test_import_liberty_restrictions_seed.py`
  - `tests/test_report_liberty_restrictions_status.py`
  - `tests/test_export_liberty_restrictions_snapshot.py`

## Ejecución reproducible
Base temporal usada para evidencia:
- `tmp/aiops130/liberty_map_20260223T202028Z.db`

Corrida:
- validate/import de `sanction_norms_seed_v1`
- validate/import de `liberty_restrictions_seed_v1`
- reporte status con `rights_with_data_min=1.0`
- check estricto con `just parl-check-liberty-focus-gate`
- fail-path estricto con `rights_with_data_min=1.1`
- unit tests focalizados + `just parl-test-liberty-restrictions`

## Resultados
- Validación seed restricciones: `valid=true`, `fragment_assessments_total=11`, `right_categories_total=6`.
- Import restricciones: `assessments_inserted=11`, `assessments_total=11`, `fragments_with_irlc_total=8`.
- Status (umbral 1.0):
  - `status=ok`
  - `right_categories_with_data_total=6`
  - `right_categories_with_data_pct=1.0`
  - `rights_with_data_gate=true`
  - `focus_gate.passed=true`
- Fail-path (umbral 1.1):
  - `status=degraded`
  - `rights_with_data_gate=false`
  - `focus_gate.passed=false`
  - `just parl-check-liberty-focus-gate` retorna `exit=2`
- Test suite:
  - subset focal: `Ran 9 tests ... OK (skipped=1)`
  - suite completa derechos: `Ran 51 tests ... OK (skipped=1)`

## Evidencia
- `docs/etl/sprints/AI-OPS-130/evidence/sanction_norms_seed_validate_20260223T202028Z.json`
- `docs/etl/sprints/AI-OPS-130/evidence/sanction_norms_seed_import_20260223T202028Z.json`
- `docs/etl/sprints/AI-OPS-130/evidence/liberty_restrictions_validate_20260223T202028Z.json`
- `docs/etl/sprints/AI-OPS-130/evidence/liberty_restrictions_import_20260223T202028Z.json`
- `docs/etl/sprints/AI-OPS-130/evidence/liberty_restrictions_status_20260223T202028Z.json`
- `docs/etl/sprints/AI-OPS-130/evidence/liberty_restrictions_status_strict_fail_20260223T202028Z.json`
- `docs/etl/sprints/AI-OPS-130/evidence/just_parl_check_liberty_focus_gate_20260223T202028Z.txt`
- `docs/etl/sprints/AI-OPS-130/evidence/just_parl_check_liberty_focus_gate_fail_20260223T202028Z.txt`
- `docs/etl/sprints/AI-OPS-130/evidence/just_parl_check_liberty_focus_gate_fail_rc_20260223T202028Z.txt`
- `docs/etl/sprints/AI-OPS-130/evidence/unittest_liberty_right_map_20260223T202028Z.txt`
- `docs/etl/sprints/AI-OPS-130/evidence/just_parl_test_liberty_restrictions_20260223T202028Z.txt`

## Estado
DONE (cierre del gap de categorías vacías en el mapa por derecho; pendiente únicamente la extensión territorial multi-fuente).
