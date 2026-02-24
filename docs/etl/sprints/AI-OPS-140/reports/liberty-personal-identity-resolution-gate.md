# AI-OPS-140 - Derechos: gate de resolucion de identidad en scoring personal

## Objetivo del slice
Avanzar la fila `103` (scoring personal) hacia identidad real persona/cargo incorporando una métrica y gate explícitos de resolución de identidad para edges indirectos.

## Implementacion
- `scripts/report_liberty_personal_accountability_scores.py`:
  - añade `indirect_identity_resolution_pct` (matching exacto normalizado entre `actor_person_name` y `persons.full_name`),
  - añade `totals.indirect_person_edges_identity_resolved_total`,
  - añade check `indirect_identity_resolution_gate`,
  - añade muestra operativa `indirect_identity_unresolved_sample` para priorizar mapeos.
- Contrato de umbrales:
  - nuevos flags CLI:
    - `--indirect-identity-resolution-min-pct` (default `0.0`, modo observabilidad),
    - `--min-indirect-identity-resolution-edges` (default `1`).
- `justfile`:
  - nuevas variables `LIBERTY_PERSONAL_INDIRECT_IDENTITY_RESOLUTION_MIN_PCT` y `LIBERTY_PERSONAL_MIN_INDIRECT_IDENTITY_RESOLUTION_EDGES`,
  - `parl-report-liberty-personal-accountability-scores` y `parl-check-liberty-personal-accountability-gate` pasan estos parámetros.
- Tests:
  - `tests/test_report_liberty_personal_accountability_scores.py` añade caso de fail contractual para identidad imposible.

## Resultado de corrida (20260223T214658Z)
- Pass (observabilidad):
  - `status=ok`
  - `gate_passed=true`
  - `indirect_person_edges_valid_window_total=9`
  - `indirect_person_edges_identity_resolved_total=0`
  - `indirect_identity_resolution_pct=0.0`
  - `indirect_identity_resolution_gate=true` (umbral default `0.0`)
  - `unresolved_sample_total=9`
- Fail-path contractual:
  - `--indirect-identity-resolution-min-pct 1.0 --enforce-gate`
  - `status=degraded`
  - `indirect_identity_resolution_gate=false`
  - `exit=2`

## Evidencia
- Contrato identidad:
  - `docs/etl/sprints/AI-OPS-140/evidence/liberty_personal_accountability_identity_gate_20260223T214658Z.json`
  - `docs/etl/sprints/AI-OPS-140/evidence/liberty_personal_accountability_identity_contract_20260223T214658Z.json`
  - `docs/etl/sprints/AI-OPS-140/evidence/liberty_personal_accountability_identity_gate_fail_20260223T214658Z.json`
  - `docs/etl/sprints/AI-OPS-140/evidence/liberty_personal_accountability_identity_gate_fail_rc_20260223T214658Z.txt`
- Seed/import reproducible:
  - `docs/etl/sprints/AI-OPS-140/evidence/just_parl_import_sanction_norms_seed_20260223T214658Z.txt`
  - `docs/etl/sprints/AI-OPS-140/evidence/just_parl_import_liberty_restrictions_seed_20260223T214658Z.txt`
  - `docs/etl/sprints/AI-OPS-140/evidence/just_parl_import_liberty_indirect_accountability_seed_20260223T214658Z.txt`
- Tests:
  - `docs/etl/sprints/AI-OPS-140/evidence/unittest_liberty_personal_identity_contract_20260223T214658Z.txt`
  - `docs/etl/sprints/AI-OPS-140/evidence/just_parl_test_liberty_restrictions_20260223T214658Z.txt`

## Comando de continuidad
```bash
DB_PATH=<db> SNAPSHOT_DATE=2026-02-23 just parl-check-liberty-personal-accountability-gate
```
