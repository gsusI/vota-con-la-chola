# AI-OPS-155 - Lineage normativo reproducible (`deroga/modifica/desarrolla`) en lane sancionador

## Donde estamos ahora
- El lane `parl-sanction-norms-seed-pipeline` ya cubria `norma -> fragmento -> responsabilidad` con evidencia primaria.
- Seguía abierto el gap de lineage normativo por versión/fecha (`deroga/modifica/desarrolla`) en la fila `Normativa por fragmento`.

## A donde vamos
- Mantener el mismo pipeline reproducible y añadir una capa auditable de lineage entre normas.
- Exigir evidencia primaria fechada para cada edge de lineage y visibilizar cobertura en el reporte operativo.

## Cambios entregados
- Schema aditivo:
  - Nueva tabla `legal_norm_lineage_edges` en `etl/load/sqlite_schema.sql`.
  - Índices nuevos por `norm_id`, `related_norm_id` y `relation_type`.
- Contrato de semilla (`validate_sanction_norms_seed.py`):
  - Nuevo bloque opcional `lineage_hints` por norma.
  - Validaciones para `relation_type`, target (`target_boe_id`/`target_norm_id`), `source_url`, `evidence_date`, `evidence_quote`.
  - Métrica nueva: `lineage_hints_total`.
- Import (`import_sanction_norms_seed.py`):
  - Upsert de edges en `legal_norm_lineage_edges`.
  - Alta automática de normas relacionadas referenciadas por lineage (`lineage_related_norms_inserted`) cuando no existen aún en `legal_norms`.
  - Contadores nuevos: `lineage_edges_inserted/updated` y `legal_norm_lineage_edges_total`.
- Status (`report_sanction_norms_seed_status.py`):
  - KPIs de lineage: `lineage_edges_total`, cobertura por norma, cobertura de evidencia primaria.
  - Checks nuevos: `lineage_chain_started`, `all_norms_with_lineage`, `all_lineage_edges_with_primary_evidence`.
  - Breakdown por tipo: `by_relation_type`.
- Guardrail de foco `Derechos`:
  - `report_liberty_restrictions_status.py` pasa a calcular cobertura de normas/fuentes/ámbitos sobre normas con fragmentos (join base `legal_norm_fragments`) para que referencias lineage sin fragmentación (`lineage_ref`) no degraden artificialmente el `focus_gate`.
- Semilla v1 actualizada (`etl/data/seeds/sanction_norms_seed_v1.json`):
  - Se añade `lineage_hints` para las 8 normas del piloto con evidencia fechada.

## Validacion
- Tests focales del lane (`validate/import/report`):
  - `Ran 8`, `OK`
  - Evidencia: `docs/etl/sprints/AI-OPS-155/evidence/unittest_sanction_norms_seed_20260224T000517Z.txt`
- Suite completa `Derechos` (regresión):
  - `Ran 100`, `OK (skipped=1)`
  - Evidencia: `docs/etl/sprints/AI-OPS-155/evidence/just_parl_test_liberty_restrictions_20260224T001159Z.txt`
- Corrida real pipeline (`DB_PATH=etl/data/staging/politicos-es.db`, `SNAPSHOT_DATE=2026-02-24`):
  - Validación semilla: `lineage_hints_total=8`.
  - Import: `lineage_related_norms_inserted=4`, `lineage_edges_inserted=8`, `legal_norm_lineage_edges_total=8`.
  - Status: `status=ok`, `norms_with_lineage=8/8`, `lineage_primary_evidence_coverage_pct=1.0`.
  - Evidencia:
    - `docs/etl/sprints/AI-OPS-155/evidence/sanction_norms_seed_validate_20260224T000517Z.json`
    - `docs/etl/sprints/AI-OPS-155/evidence/sanction_norms_seed_import_20260224T000517Z.json`
    - `docs/etl/sprints/AI-OPS-155/evidence/sanction_norms_seed_status_20260224T000517Z.json`
    - `docs/etl/sprints/AI-OPS-155/evidence/just_parl_sanction_norms_seed_pipeline_20260224T000517Z.txt`
- Integridad:
  - `PRAGMA foreign_key_check` sin violaciones (`fk_violations_total=0`).
  - Evidencia: `docs/etl/sprints/AI-OPS-155/evidence/sqlite_fk_check_20260224T000533Z.json`

## Siguiente paso
- Pasar de semilla a ingesta BOE consolidada por versión/fecha (histórico completo de relaciones).
- Enriquecer `lineage_hints` con soporte explícito para `modifica` en cobertura multi-boletín (Estado+CCAA+municipal) dentro del foco `Derechos`.
