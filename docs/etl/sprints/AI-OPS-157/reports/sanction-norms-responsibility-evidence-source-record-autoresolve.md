# AI-OPS-157 - Trazabilidad `source_record_pk` en evidencia de responsabilidades normativas

## Donde estamos ahora
- El lane sancionador ya soporta evidencia multipista por edge (`AI-OPS-156`) en `legal_fragment_responsibility_evidence`.
- Faltaba cerrar el loop operativo para rellenar `source_record_pk` sin trabajo manual cuando la semilla ya trae referencia estable `source_id + source_record_id`.

## A donde vamos
- Elevar trazabilidad documental por edge en `norma -> fragmento -> responsabilidad -> evidencia`.
- Mantener import idempotente y observabilidad explicita de cobertura de `source_record_pk` en el status lane.

## Cambios entregados
- Import con autoresolucion de `source_record_pk`:
  - `scripts/import_sanction_norms_seed.py` ahora resuelve `source_record_pk` desde `source_records` cuando `evidence_items[]` trae `source_id + source_record_id`.
  - Se añade cache en memoria por clave `(source_id, source_record_id)` para evitar N+1 en lookup.
  - Nuevos contadores en import:
    - `responsibility_evidence_source_record_pk_auto_resolved`
    - `responsibility_evidence_source_record_pk_auto_resolve_missed`
- Contrato de validacion para referencias de evidencia:
  - `scripts/validate_sanction_norms_seed.py` valida opcionales en `responsibility_hints[].evidence_items[]`:
    - `source_record_id` no vacio y con `source_id` obligatorio
    - `source_record_pk` entero positivo cuando se declara
- Observabilidad en status report:
  - `scripts/report_sanction_norms_seed_status.py` añade metricas de trazabilidad por evidencia:
    - `responsibility_evidence_items_with_source_record_total`
    - `responsibility_evidence_items_missing_source_record`
    - `responsibility_evidence_item_source_record_coverage_pct`
    - check informativo `responsibility_evidence_source_record_chain_started`
- Tests actualizados:
  - `tests/test_import_sanction_norms_seed.py` valida autoresolucion real desde `source_records`.
  - `tests/test_validate_sanction_norms_seed.py` valida errores de contrato para refs `source_record_*` invalidas.
  - `tests/test_report_sanction_norms_seed_status.py` valida nuevas metricas de cobertura de `source_record_pk`.

## Validacion
- Tests focales lane sancionador:
  - `just parl-test-sanction-norms-seed` -> `Ran 10`, `OK`.
  - Evidencia: `docs/etl/sprints/AI-OPS-157/evidence/just_parl_test_sanction_norms_seed_20260224T002457Z.txt`
- Corrida real de pipeline (DB real):
  - Import: `responsibility_evidence_source_record_pk_auto_resolved=0`, `responsibility_evidence_source_record_pk_auto_resolve_missed=0`
  - Status: `responsibility_evidence_items_with_source_record_total=0/15`, `responsibility_evidence_item_source_record_coverage_pct=0.0`, `status=ok`
  - Evidencia:
    - `docs/etl/sprints/AI-OPS-157/evidence/sanction_norms_seed_validate_20260224T002457Z.json`
    - `docs/etl/sprints/AI-OPS-157/evidence/sanction_norms_seed_import_20260224T002457Z.json`
    - `docs/etl/sprints/AI-OPS-157/evidence/sanction_norms_seed_status_20260224T002457Z.json`
    - `docs/etl/sprints/AI-OPS-157/evidence/just_parl_sanction_norms_seed_pipeline_20260224T002457Z.txt`
- Integridad:
  - `PRAGMA foreign_key_check`: `fk_violations_total=0`
  - Evidencia: `docs/etl/sprints/AI-OPS-157/evidence/sqlite_fk_check_20260224T002457Z.json`
- Suite completa `Derechos`:
  - `Ran 100`, `OK (skipped=1)`.
  - Evidencia: `docs/etl/sprints/AI-OPS-157/evidence/just_parl_test_liberty_restrictions_20260224T002457Z.txt`

## Siguiente paso
- Poblar `evidence_items` con referencias reales `source_id + source_record_id` (Congreso/Senado/BOE) para subir `responsibility_evidence_item_source_record_coverage_pct` desde `0.0`.
- Endurecer gate cuando exista volumen suficiente de evidencia multi-fuente (`min rows` + `min pct`) para que la trazabilidad documental por edge sea exigible y no solo observable.
