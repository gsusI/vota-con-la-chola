# AI-OPS-156 - Evidencia multipista por responsabilidad normativa

## Donde estamos ahora
- El lane sancionador ya tenía responsabilidades por fragmento con evidencia primaria mínima (`source_url`, `evidence_date`, `evidence_quote`) y lineage operativo (`AI-OPS-155`).
- Faltaba una estructura reproducible para guardar evidencia múltiple por edge de responsabilidad (no solo un bloque plano en `responsibility_hints`).

## A donde vamos
- Elevar la trazabilidad del lane `norma -> fragmento -> responsabilidad` con una tabla específica de evidencias por responsabilidad.
- Mantener el pipeline único (`just parl-sanction-norms-seed-pipeline`) y reforzar checks de cobertura en el status report.

## Cambios entregados
- Schema aditivo:
  - Nueva tabla `legal_fragment_responsibility_evidence` en `etl/load/sqlite_schema.sql`.
  - Índices: `idx_legal_fragment_responsibility_evidence_responsibility_id`, `idx_legal_fragment_responsibility_evidence_type`.
- Contrato de semilla:
  - `validate_sanction_norms_seed.py` añade soporte opcional para `responsibility_hints[].evidence_items[]`.
  - Validación de `evidence_type`, `source_url`, `evidence_date`, `evidence_quote`.
  - Métrica nueva: `responsibility_evidence_items_total`.
- Import:
  - `import_sanction_norms_seed.py` inserta/upserta evidencias por responsabilidad en `legal_fragment_responsibility_evidence`.
  - Si un hint no trae `evidence_items`, genera una evidencia por defecto (`boe_publicacion`) con los campos primarios del hint para no perder cobertura.
  - Contadores nuevos: `responsibility_evidence_inserted`, `responsibility_evidence_updated`.
- Status:
  - `report_sanction_norms_seed_status.py` añade KPIs/checks de evidencia multipista:
    - `responsibilities_with_evidence_items_total`
    - `responsibility_evidence_items_total`
    - `responsibility_evidence_items_with_primary_fields_total`
    - coberturas `responsibility_evidence_item_coverage_pct` y `responsibility_evidence_item_primary_fields_coverage_pct`
    - checks `all_responsibilities_with_evidence_items` y `all_responsibility_evidence_items_with_primary_fields`.
- Guardrail de regresión `Derechos`:
  - Se mantiene el ajuste de `report_liberty_restrictions_status.py` (cobertura sobre normas con fragmentos) y se añade test explícito para excluir normas sin fragmentación del denominador.

## Validacion
- Tests focales lane sancionador:
  - `just parl-test-sanction-norms-seed` -> `Ran 9`, `OK`.
  - Evidencia: `docs/etl/sprints/AI-OPS-156/evidence/just_parl_test_sanction_norms_seed_20260224T001801Z.txt`
- Corrida real de pipeline (DB real):
  - Import:
    - `responsibility_evidence_inserted=15`
    - `legal_fragment_responsibility_evidence_total=15`
  - Status:
    - `responsibilities_with_evidence_items_total=15/15`
    - `responsibility_evidence_items_with_primary_fields_total=15/15`
    - `status=ok`
  - Evidencia:
    - `docs/etl/sprints/AI-OPS-156/evidence/sanction_norms_seed_validate_20260224T001801Z.json`
    - `docs/etl/sprints/AI-OPS-156/evidence/sanction_norms_seed_import_20260224T001801Z.json`
    - `docs/etl/sprints/AI-OPS-156/evidence/sanction_norms_seed_status_20260224T001801Z.json`
    - `docs/etl/sprints/AI-OPS-156/evidence/just_parl_sanction_norms_seed_pipeline_20260224T001801Z.txt`
- Integridad:
  - `PRAGMA foreign_key_check`: `fk_violations_total=0`.
  - Evidencia: `docs/etl/sprints/AI-OPS-156/evidence/sqlite_fk_check_20260224T001813Z.json`
- Suite completa `Derechos`:
  - `Ran 100`, `OK (skipped=1)`.
  - Evidencia: `docs/etl/sprints/AI-OPS-156/evidence/just_parl_test_liberty_restrictions_20260224T001822Z.txt`

## Siguiente paso
- Enriquecer `evidence_items` con referencias multi-fuente reales (Congreso/Senado/BOE por edge) y no solo fallback derivado del hint.
- Conectar `source_record_pk` en evidencias cuando exista mapeo reproducible BOE para cerrar trazabilidad documental completa por edge.
