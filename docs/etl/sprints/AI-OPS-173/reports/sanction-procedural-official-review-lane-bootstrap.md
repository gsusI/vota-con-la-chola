# AI-OPS-173 — Bootstrap de lane oficial TEAR/TEAC/contencioso/defensor

## Objetivo
Avanzar `Scenario A` sin depender de desbloqueos externos: abrir lane controlable para pasar garantias procedimentales de seed/piloto a fuentes oficiales de revision (`TEAR/TEAC/contencioso/defensor`) con backlog accionable reproducible.

## Entregado
- Seed de catalogo ampliada (`etl/data/seeds/sanction_data_catalog_seed_v1.json`) con 4 fuentes oficiales nuevas:
  - `es:sanctions:tear_resolutions`
  - `es:sanctions:teac_resolutions`
  - `es:sanctions:contencioso_sentencias`
  - `es:sanctions:defensor_pueblo_quejas`
- Script nuevo: `scripts/report_sanction_procedural_official_review_status.py`.
- Test nuevo: `tests/test_report_sanction_procedural_official_review_status.py`.
- Lanes `just` nuevos/integrados:
  - `parl-report-sanction-procedural-official-review-status`
  - integración en `parl-sanction-data-catalog-pipeline`
  - integración en `parl-test-sanction-data-catalog`

## Resultado de corrida (20260224T095551Z)
- Catalogo validado e importado con `volume_sources_total=9` (`+4` oficiales).
- Estado lane oficial procedimental: `degraded` (esperado en bootstrap).
- Cobertura de seed de fuentes oficiales: `4/4` (`official_review_source_seed_coverage_pct=1.0`).
- Cobertura de métricas oficiales: `0/4` (`official_review_source_metric_coverage_pct=0.0`).
- Cola accionable generada en CSV con 4 filas, todas en `status=no_metrics` y `next_action=ingest_official_review_procedural_metrics`.

## Conclusion operativa
Se cierra el bootstrap controlable y queda explicitado el siguiente lote de extracción oficial sin ambigüedad. El lane ya diferencia entre “fuente no sembrada”, “sin métricas” y “sin trazabilidad source_record”, habilitando ejecución incremental por sprint.

## Evidencia
- `docs/etl/sprints/AI-OPS-173/evidence/sanction_data_catalog_validate_20260224T095551Z.json`
- `docs/etl/sprints/AI-OPS-173/evidence/sanction_data_catalog_import_20260224T095551Z.json`
- `docs/etl/sprints/AI-OPS-173/evidence/sanction_data_catalog_status_20260224T095551Z.json`
- `docs/etl/sprints/AI-OPS-173/evidence/sanction_procedural_official_review_status_20260224T095551Z.json`
- `docs/etl/sprints/AI-OPS-173/exports/sanction_procedural_official_review_queue_20260224T095551Z.csv`
- `docs/etl/sprints/AI-OPS-173/evidence/just_parl_test_sanction_data_catalog_20260224T095551Z.txt`
- `docs/etl/sprints/AI-OPS-173/evidence/just_parl_test_sanction_volume_pilot_20260224T095551Z.txt`
