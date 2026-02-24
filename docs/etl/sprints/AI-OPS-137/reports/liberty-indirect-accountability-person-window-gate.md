# AI-OPS-137 - Derechos: cadena indirecta con persona/cargo y ventana temporal

## Objetivo del slice
Cerrar un gap operativo de `Derechos/Responsabilidad indirecta` (tracker fila `102`) incorporando contrato auditable de persona/cargo + ventana temporal en la cadena causal indirecta, con gate estricto reproducible.

## Implementacion
- Esquema SQLite:
  - `liberty_indirect_responsibility_edges` añade columnas aditivas:
    - `actor_person_name`
    - `actor_role_title`
    - `appointment_start_date`
    - `appointment_end_date`
  - Compat forward en `etl/politicos_es/db.py` (`ensure_schema_compat`) para DBs existentes.
- Contrato de semilla:
  - `validate_liberty_indirect_accountability_seed.py` valida:
    - formato fecha `YYYY-MM-DD` para `evidence_date` y ventana,
    - `appointment_end_date >= appointment_start_date`,
    - consistencia temporal `evidence_date` dentro de la ventana cuando aplica,
    - presencia de `actor_person_name/actor_role_title/appointment_start_date` si se usa contexto persona-ventana.
- Ingesta:
  - `import_liberty_indirect_accountability_seed.py` persiste nuevos campos en upsert idempotente.
- Status + gate:
  - `report_liberty_indirect_accountability_status.py` añade:
    - `attributable_edges_with_actor_person_total`
    - `attributable_edges_with_valid_person_window_total`
    - `attributable_edges_with_valid_person_window_pct`
    - check/gate `indirect_person_window_gate`
  - `justfile` propaga thresholds:
    - `LIBERTY_INDIRECT_PERSON_WINDOW_MIN` (default `1.0`)
    - `LIBERTY_INDIRECT_MIN_PERSON_WINDOW_EDGES` (default `1`)
- Publicacion snapshot:
  - `export_liberty_restrictions_snapshot.py` expone en `indirect_accountability_edges`:
    - `actor_person_name`
    - `actor_role_title`
    - `appointment_start_date`
    - `appointment_end_date`
- Seed:
  - `etl/data/seeds/liberty_indirect_accountability_seed_v1.json` actualizado con persona/cargo+ventana para la muestra actual.

## Resultado de corrida (20260223T212645Z)
- Estado principal:
  - `status=ok`
  - `edges_total=12`
  - `attributable_edges_total=9`
  - `fragments_with_attributable_edges_total=7/8`
  - `attributable_edges_with_actor_person_total=9`
  - `attributable_edges_with_valid_person_window_total=9`
  - `attributable_edges_with_valid_person_window_pct=1.0`
  - `gate.passed=true`
- Fail-path contractual:
  - Threshold imposible (`person_window_min=1.1`, `min_edges=20`)
  - `status=degraded`
  - `indirect_person_window_gate=false`
  - `exit=2`

## Evidencia
- Status/gate:
  - `docs/etl/sprints/AI-OPS-137/evidence/liberty_indirect_status_20260223T212645Z.json`
  - `docs/etl/sprints/AI-OPS-137/evidence/liberty_indirect_gate_20260223T212645Z.json`
  - `docs/etl/sprints/AI-OPS-137/evidence/liberty_indirect_gate_person_window_fail_20260223T212645Z.json`
  - `docs/etl/sprints/AI-OPS-137/evidence/liberty_indirect_gate_person_window_fail_rc_20260223T212645Z.txt`
- Import/validate:
  - `docs/etl/sprints/AI-OPS-137/evidence/liberty_indirect_validate_20260223T212645Z.json`
  - `docs/etl/sprints/AI-OPS-137/evidence/liberty_indirect_import_20260223T212645Z.json`
- Snapshot con campos nuevos expuestos:
  - `docs/etl/sprints/AI-OPS-137/evidence/liberty_restrictions_snapshot_20260223_ai_ops_137_20260223T212645Z.json`
- Tests:
  - `docs/etl/sprints/AI-OPS-137/evidence/unittest_liberty_indirect_contract_20260223T212645Z.txt`
  - `docs/etl/sprints/AI-OPS-137/evidence/just_parl_test_sanction_norms_seed_20260223T212645Z.txt`
  - `docs/etl/sprints/AI-OPS-137/evidence/just_parl_test_liberty_restrictions_20260223T212645Z.txt`

## Comando de continuidad
```bash
DB_PATH=<db> SNAPSHOT_DATE=2026-02-23 just parl-report-liberty-indirect-accountability-status
```
