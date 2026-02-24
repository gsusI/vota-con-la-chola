# AI-OPS-159 - Split de procedencia `seed` vs `non-seed` en `source_record_pk` de evidencia sancionadora

## Donde estamos ahora
- El lane sancionador ya cerró cobertura documental al `100%` para `source_record_pk` en evidencia multipista (AI-OPS-158).
- Faltaba observabilidad explícita para distinguir cuánto de esa cobertura provenía de filas bootstrap de semilla vs filas no-seed (`ingesta real`), evitando falsos verdes de trazabilidad.

## A donde vamos
- Mantener cobertura total `source_record_pk` y exponer composición de procedencia para guiar la migración de bootstrap semilla hacia cadenas multi-fuente reales.
- Endurecer contrato con test de regresión para el caso `non-seed`.

## Cambios entregados
- Status del lane enriquecido en `scripts/report_sanction_norms_seed_status.py`:
  - Nuevos totales:
    - `responsibility_evidence_items_with_seed_source_record_total`
    - `responsibility_evidence_items_with_non_seed_source_record_total`
  - Nueva cobertura:
    - `responsibility_evidence_item_non_seed_source_record_coverage_pct`
  - Nuevo check informativo:
    - `responsibility_evidence_non_seed_source_record_chain_started`
- Cobertura de tests reforzada en `tests/test_report_sanction_norms_seed_status.py`:
  - Nuevo caso `test_report_marks_non_seed_source_records_when_present` que fuerza un `source_record` no-seed y valida métricas/checks de split.

## Validacion
- Corrida real de pipeline (DB real):
  - `responsibility_evidence_items_total=15`
  - `responsibility_evidence_items_with_source_record_total=15`
  - `responsibility_evidence_items_with_seed_source_record_total=15`
  - `responsibility_evidence_items_with_non_seed_source_record_total=0`
  - `responsibility_evidence_item_source_record_coverage_pct=1.0`
  - `responsibility_evidence_item_non_seed_source_record_coverage_pct=0.0`
  - `responsibility_evidence_non_seed_source_record_chain_started=false`
  - `status=ok`
- Import counters (misma corrida):
  - `responsibility_evidence_source_record_pk_auto_resolved=15`
  - `responsibility_evidence_source_record_seed_rows_inserted=0`
  - `responsibility_evidence_source_record_pk_auto_resolve_missed=0`
- Integridad:
  - `PRAGMA foreign_key_check`: `fk_violations_total=0`
- Tests:
  - `just parl-test-sanction-norms-seed` -> `Ran 12`, `OK`
  - `just parl-test-liberty-restrictions` -> `Ran 100`, `OK (skipped=1)`

Evidencia:
- `docs/etl/sprints/AI-OPS-159/evidence/sanction_norms_seed_validate_20260224T003834Z.json`
- `docs/etl/sprints/AI-OPS-159/evidence/sanction_norms_seed_import_20260224T003834Z.json`
- `docs/etl/sprints/AI-OPS-159/evidence/sanction_norms_seed_status_20260224T003834Z.json`
- `docs/etl/sprints/AI-OPS-159/evidence/sanction_norms_seed_non_seed_source_record_contract_summary_20260224T003834Z.json`
- `docs/etl/sprints/AI-OPS-159/evidence/just_parl_sanction_norms_seed_pipeline_20260224T003834Z.txt`
- `docs/etl/sprints/AI-OPS-159/evidence/sqlite_fk_check_20260224T003834Z.json`
- `docs/etl/sprints/AI-OPS-159/evidence/just_parl_test_sanction_norms_seed_20260224T003834Z.txt`
- `docs/etl/sprints/AI-OPS-159/evidence/just_parl_test_liberty_restrictions_20260224T003834Z.txt`

## Siguiente paso
- Introducir en ingestas reales (Congreso/Senado/BOE) referencias directas `source_id + source_record_id` en los edges de evidencia para elevar `responsibility_evidence_items_with_non_seed_source_record_total` y reducir dependencia de bootstrap seed.
