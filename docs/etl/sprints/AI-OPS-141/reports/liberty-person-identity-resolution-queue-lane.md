# AI-OPS-141 - Derechos: cola operativa de resolucion de identidad personal

## Objetivo del slice
Avanzar la fila `103` (scoring personal) desde observabilidad pasiva de identidad no resuelta a una cola accionable y reproducible para resolver `actor_person_name -> person_id`.

## Implementacion
- Nuevo lane: `scripts/report_liberty_person_identity_resolution_queue.py`
  - filtra edges indirectos atribuibles con ventana temporal valida (`actor_person_name`, `actor_role_title`, `appointment_start_date/end_date`, `evidence_date`),
  - calcula `indirect_identity_resolution_pct` y `indirect_identity_unresolved_pct`,
  - publica cola de no resueltos priorizada por `edges_total` con `queue_key` estable por actor.
- Export operativa:
  - JSON con `totals/coverage/checks/gate` y `queue_rows`,
  - CSV para trabajo manual de resolución (`queue_rank`, `actor_person_name`, `actor_role_titles_csv`, `edges_total`, `fragments_total`, fechas de evidencia).
- Contrato en `justfile`:
  - variables nuevas `LIBERTY_PERSON_IDENTITY_RESOLUTION_*`,
  - lanes nuevos `parl-report-liberty-person-identity-resolution-queue` y `parl-check-liberty-person-identity-resolution-gate`,
  - integración en `parl-liberty-restrictions-pipeline`.
- Tests:
  - `tests/test_report_liberty_person_identity_resolution_queue.py` (ok/degraded y mejora de resolución al insertar match en `persons`),
  - inclusión en `just parl-test-liberty-restrictions`.

## Resultado de corrida (20260223T215635Z)
- Pass (modo operable por defecto):
  - `status=ok`
  - `gate_passed=true`
  - `indirect_person_edges_valid_window_total=9`
  - `indirect_person_edges_identity_resolved_total=0`
  - `indirect_identity_resolution_pct=0.0`
  - `indirect_identity_unresolved_pct=1.0`
  - `queue_rows_total=9` (`queue_truncated=false`)
- Fail-path contractual:
  - `LIBERTY_PERSON_IDENTITY_RESOLUTION_MIN_PCT=1.0` + `--enforce-gate`
  - `status=degraded`
  - `identity_resolution_gate=false`
  - `exit=2`
- Tests:
  - focales: `Ran 11`, `OK (skipped=1)`
  - suite completa `Derechos`: `Ran 69`, `OK (skipped=1)`

## Evidencia
- Cola y contrato:
  - `docs/etl/sprints/AI-OPS-141/evidence/liberty_person_identity_resolution_queue_20260223T215635Z.json`
  - `docs/etl/sprints/AI-OPS-141/evidence/liberty_person_identity_resolution_queue_gate_20260223T215635Z.json`
  - `docs/etl/sprints/AI-OPS-141/evidence/liberty_person_identity_resolution_queue_fail_20260223T215635Z.json`
  - `docs/etl/sprints/AI-OPS-141/evidence/liberty_person_identity_resolution_queue_contract_20260223T215635Z.json`
  - `docs/etl/sprints/AI-OPS-141/evidence/just_parl_check_liberty_person_identity_resolution_gate_fail_rc_20260223T215635Z.txt`
- Seed/import reproducible:
  - `docs/etl/sprints/AI-OPS-141/evidence/just_parl_import_sanction_norms_seed_20260223T215635Z.txt`
  - `docs/etl/sprints/AI-OPS-141/evidence/just_parl_import_liberty_restrictions_seed_20260223T215635Z.txt`
  - `docs/etl/sprints/AI-OPS-141/evidence/just_parl_import_liberty_indirect_accountability_seed_20260223T215635Z.txt`
- Export cola:
  - `docs/etl/sprints/AI-OPS-141/exports/liberty_person_identity_resolution_queue_20260223T215635Z.csv`
  - `docs/etl/sprints/AI-OPS-141/exports/liberty_person_identity_resolution_queue_latest.csv`
- Tests:
  - `docs/etl/sprints/AI-OPS-141/evidence/unittest_liberty_person_identity_resolution_queue_contract_20260223T215635Z.txt`
  - `docs/etl/sprints/AI-OPS-141/evidence/just_parl_test_liberty_restrictions_20260223T215635Z.txt`

## Comando de continuidad
```bash
DB_PATH=<db> SNAPSHOT_DATE=2026-02-23 just parl-check-liberty-person-identity-resolution-gate
```
