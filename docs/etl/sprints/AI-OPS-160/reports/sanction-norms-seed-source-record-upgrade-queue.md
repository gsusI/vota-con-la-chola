# AI-OPS-160 - Cola accionable para migrar `source_record_pk` de seed a ingesta real

## Donde estamos ahora
- La cobertura documental por `source_record_pk` ya está al `100%` en el lane sancionador (`15/15`), pero toda la procedencia sigue en filas seed (`seed=15`, `non-seed=0`).
- El split introducido en AI-OPS-159 detecta el gap, pero faltaba una cola operativa reproducible para ejecutarlo.

## A donde vamos
- Convertir el gap `seed -> non-seed` en backlog accionable por evidencia (`norma -> fragmento -> responsabilidad -> evidence_item`) con export JSON/CSV reproducible.
- Mantener trazabilidad explícita sin romper la cobertura actual.

## Cambios entregados
- Nuevo exportador de cola:
  - `scripts/export_sanction_norms_seed_source_record_upgrade_queue.py`
  - Detecta filas en `legal_fragment_responsibility_evidence` cuyo `source_record_pk` apunta a `source_records.raw_payload` marcado como seed (`seed_schema_version=sanction_norms_seed_v1`).
  - Exporta cola con `queue_key` estable (`responsibility_evidence_id:<id>`), contexto normativo y `next_action`.
- Integración en `justfile`:
  - Nuevos vars/outputs:
    - `SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_OUT`
    - `SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_CSV_OUT`
    - `SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_LIMIT`
    - `SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_SEED_SCHEMA_VERSION`
  - Nuevo lane:
    - `parl-export-sanction-norms-seed-source-record-upgrade-queue`
  - `parl-sanction-norms-seed-pipeline` ahora ejecuta export de cola tras status.
- Tests:
  - `tests/test_export_sanction_norms_seed_source_record_upgrade_queue.py`
    - verifica cola vacía cuando el `source_record` es no-seed.
    - verifica cola visible cuando el `source_record` proviene de seed.
  - `parl-test-sanction-norms-seed` incorpora el nuevo archivo de tests.

## Validacion
- Corrida de cierre (`20260224T004510Z`):
  - Lane status: `ok`
  - Queue status: `degraded` (hay backlog)
  - `responsibility_evidence_items_total=15`
  - `responsibility_evidence_items_with_source_record_total=15`
  - split procedencia: `seed=15`, `non-seed=0`
  - `seed_upgrade_queue_rows_total=15`
  - `seed_upgrade_queue_norms_total=8`
  - `seed_upgrade_queue_fragments_total=8`
  - `seed_upgrade_queue_responsibilities_total=15`
- Integridad:
  - `PRAGMA foreign_key_check`: `fk_violations_total=0`
- Tests:
  - `just parl-test-sanction-norms-seed` -> `Ran 14`, `OK`
  - `just parl-test-liberty-restrictions` -> `Ran 100`, `OK (skipped=1)`

Evidencia:
- `docs/etl/sprints/AI-OPS-160/evidence/sanction_norms_seed_validate_20260224T004510Z.json`
- `docs/etl/sprints/AI-OPS-160/evidence/sanction_norms_seed_import_20260224T004510Z.json`
- `docs/etl/sprints/AI-OPS-160/evidence/sanction_norms_seed_status_20260224T004510Z.json`
- `docs/etl/sprints/AI-OPS-160/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T004510Z.json`
- `docs/etl/sprints/AI-OPS-160/exports/sanction_norms_seed_source_record_upgrade_queue_20260224T004510Z.csv`
- `docs/etl/sprints/AI-OPS-160/evidence/sanction_norms_seed_source_record_upgrade_queue_contract_summary_20260224T004510Z.json`
- `docs/etl/sprints/AI-OPS-160/evidence/just_parl_sanction_norms_seed_pipeline_20260224T004510Z.txt`
- `docs/etl/sprints/AI-OPS-160/evidence/sqlite_fk_check_20260224T004510Z.json`
- `docs/etl/sprints/AI-OPS-160/evidence/just_parl_test_sanction_norms_seed_20260224T004510Z.txt`
- `docs/etl/sprints/AI-OPS-160/evidence/just_parl_test_liberty_restrictions_20260224T004510Z.txt`

## Siguiente paso
- Atacar la cola `seed_upgrade_queue_rows_total=15` conectando evidencia a `source_records` de ingestas reales (BOE/Congreso/Senado) para elevar `non-seed` por lotes controlados.
