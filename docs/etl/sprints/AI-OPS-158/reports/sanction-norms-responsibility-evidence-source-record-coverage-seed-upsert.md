# AI-OPS-158 - Cobertura 100% de `source_record_pk` en evidencia de responsabilidades

## Donde estamos ahora
- El lane sancionador ya tenía evidencia multipista por responsabilidad (AI-OPS-156) y autoresolución de `source_record_pk` cuando existían refs `source_id + source_record_id` (AI-OPS-157).
- Persistía un gap operativo: la semilla no traía `evidence_items` explícitos y, por tanto, la cobertura documental en DB real seguía `0/15`.

## A donde vamos
- Cerrar trazabilidad reproducible por edge (`norma -> fragmento -> responsabilidad -> evidencia -> source_record_pk`) con cobertura completa en el lane semilla.
- Mantener comportamiento idempotente y explícito sobre qué filas se resuelven por lookup existente vs qué filas se crean como `source_records` de semilla.

## Cambios entregados
- Semilla enriquecida:
  - `etl/data/seeds/sanction_norms_seed_v1.json` añade `responsibility_hints[].evidence_items[]` para los 15 hints, con:
    - `evidence_type=boe_publicacion`
    - `source_id=boe_api_legal`
    - `source_record_id=<boe_id de la norma>`
    - `source_url/evidence_date/evidence_quote`
- Import reforzado para cubrir faltantes de `source_records`:
  - `scripts/import_sanction_norms_seed.py` añade `_ensure_source_record(...)` para crear fila en `source_records` cuando no existe y llega referencia `source_id + source_record_id`.
  - Se mantiene lookup previo cacheado (`_resolve_source_record_pk`) y se evita sobrescribir filas existentes.
  - Nuevos contadores:
    - `responsibility_evidence_source_record_seed_rows_inserted`
    - (manteniendo) `responsibility_evidence_source_record_pk_auto_resolved`
    - (manteniendo) `responsibility_evidence_source_record_pk_auto_resolve_missed`
- Validación y tests:
  - `tests/test_import_sanction_norms_seed.py` añade caso de upsert de `source_records` faltantes.
  - `tests/test_validate_sanction_norms_seed.py` y `tests/test_report_sanction_norms_seed_status.py` permanecen alineados con el contrato reforzado.

## Validacion
- Tests focales lane sancionador:
  - `just parl-test-sanction-norms-seed` -> `Ran 11`, `OK`.
  - Evidencia: `docs/etl/sprints/AI-OPS-158/evidence/just_parl_test_sanction_norms_seed_20260224T003121Z.txt`
- Corrida real de pipeline (DB real):
  - Validación seed: `responsibility_evidence_items_total=15`.
  - Import:
    - `responsibility_evidence_source_record_pk_auto_resolved=7`
    - `responsibility_evidence_source_record_seed_rows_inserted=8`
    - `responsibility_evidence_source_record_pk_auto_resolve_missed=0`
  - Status:
    - `responsibility_evidence_items_with_source_record_total=15/15`
    - `responsibility_evidence_item_source_record_coverage_pct=1.0`
    - `status=ok`
  - Evidencia:
    - `docs/etl/sprints/AI-OPS-158/evidence/sanction_norms_seed_validate_20260224T003121Z.json`
    - `docs/etl/sprints/AI-OPS-158/evidence/sanction_norms_seed_import_20260224T003121Z.json`
    - `docs/etl/sprints/AI-OPS-158/evidence/sanction_norms_seed_status_20260224T003121Z.json`
    - `docs/etl/sprints/AI-OPS-158/evidence/just_parl_sanction_norms_seed_pipeline_20260224T003121Z.txt`
- Integridad:
  - `PRAGMA foreign_key_check`: `fk_violations_total=0`.
  - Evidencia: `docs/etl/sprints/AI-OPS-158/evidence/sqlite_fk_check_20260224T003121Z.json`
- Suite completa `Derechos`:
  - `Ran 100`, `OK (skipped=1)`.
  - Evidencia: `docs/etl/sprints/AI-OPS-158/evidence/just_parl_test_liberty_restrictions_20260224T003121Z.txt`

## Siguiente paso
- Sustituir progresivamente filas `source_records` creadas desde seed por registros provenientes de ingesta BOE/Congreso/Senado para no depender de bootstrap semilla en trazabilidad documental.
- Añadir desglose en status de procedencia `source_record` (ingesta real vs seed-upsert) para controlar la calidad de la cadena documental por fuente.
