# AI-OPS-142 - Derechos: aplicacion reproducible de identidad personal indirecta

## Objetivo del slice
Cerrar el loop operativo abierto en AI-OPS-141: pasar de cola visible de no resueltos a una aplicacion reproducible de alias `actor_person_name -> person_id` que impacte scoring y queue gates.

## Implementacion
- Esquema:
  - nueva tabla `person_name_aliases` en `etl/load/sqlite_schema.sql` (`person_id`, `alias`, `canonical_alias`, trazabilidad básica).
- Contrato seed:
  - nuevo seed versionado `etl/data/seeds/liberty_person_identity_resolution_seed_v1.json` (9 alias, 5 personas destino).
  - validador `scripts/validate_liberty_person_identity_resolution_seed.py`.
  - importador `scripts/import_liberty_person_identity_resolution_seed.py`.
- Lanes `just`:
  - `parl-validate-liberty-person-identity-seed`
  - `parl-import-liberty-person-identity-seed`
  - integración en `parl-liberty-restrictions-pipeline` antes de scoring personal.
- Resolucion en reportes:
  - `scripts/report_liberty_personal_accountability_scores.py` y
  - `scripts/report_liberty_person_identity_resolution_queue.py`
  - ahora consideran identidad resuelta por:
    - match exacto `persons.full_name`, o
    - alias exacto `person_name_aliases.canonical_alias`.
  - se añade desglose de resolución `exact_name` vs `alias` en `totals`.

## Resultado de corrida (20260223T220708Z)
- Seed identity import:
  - `mappings_total=9`
  - `persons_created=5`
  - `aliases_inserted=9`
  - `aliases_total=9`
  - `persons_with_aliases_total=5`
- Scoring personal:
  - `status=ok`
  - `gate_passed=true`
  - `indirect_person_edges_valid_window_total=9`
  - `indirect_person_edges_identity_resolved_total=9`
  - `indirect_person_edges_identity_resolved_alias_total=9`
  - `indirect_identity_resolution_pct=1.0`
  - `persons_scored_total=5`
- Cola de resolución:
  - `status=ok`
  - `gate_passed=true`
  - `queue_rows_total=0`
  - `indirect_identity_resolution_pct=1.0`
- Fail-path contractual:
  - personal (`LIBERTY_PERSONAL_INDIRECT_IDENTITY_RESOLUTION_MIN_PCT=1.1`) -> `status=degraded`, `exit=2`
  - queue (`LIBERTY_PERSON_IDENTITY_RESOLUTION_MIN_PCT=1.1`) -> `status=degraded`, `exit=2`
- Tests:
  - focales: `Ran 17`, `OK (skipped=1)`
  - suite completa `Derechos`: `Ran 75`, `OK (skipped=1)`

## Evidencia
- Seed identity contract:
  - `docs/etl/sprints/AI-OPS-142/evidence/liberty_person_identity_validate_20260223T220708Z.json`
  - `docs/etl/sprints/AI-OPS-142/evidence/liberty_person_identity_import_20260223T220708Z.json`
  - `docs/etl/sprints/AI-OPS-142/evidence/liberty_person_identity_apply_contract_20260223T220708Z.json`
- Scoring/queue:
  - `docs/etl/sprints/AI-OPS-142/evidence/liberty_personal_accountability_scores_20260223T220708Z.json`
  - `docs/etl/sprints/AI-OPS-142/evidence/liberty_person_identity_resolution_queue_20260223T220708Z.json`
  - `docs/etl/sprints/AI-OPS-142/evidence/liberty_personal_accountability_scores_identity_fail_20260223T220708Z.json`
  - `docs/etl/sprints/AI-OPS-142/evidence/liberty_person_identity_resolution_queue_fail_20260223T220708Z.json`
  - `docs/etl/sprints/AI-OPS-142/evidence/just_parl_check_liberty_personal_accountability_gate_identity_fail_rc_20260223T220708Z.txt`
  - `docs/etl/sprints/AI-OPS-142/evidence/just_parl_check_liberty_person_identity_resolution_gate_fail_rc_20260223T220708Z.txt`
- Export queue:
  - `docs/etl/sprints/AI-OPS-142/exports/liberty_person_identity_resolution_queue_20260223T220708Z.csv`
- Tests:
  - `docs/etl/sprints/AI-OPS-142/evidence/unittest_liberty_person_identity_apply_contract_20260223T220708Z.txt`
  - `docs/etl/sprints/AI-OPS-142/evidence/just_parl_test_liberty_restrictions_20260223T220708Z.txt`

## Comando de continuidad
```bash
DB_PATH=<db> SNAPSHOT_DATE=2026-02-23 just parl-import-liberty-person-identity-seed && just parl-check-liberty-person-identity-resolution-gate
```
