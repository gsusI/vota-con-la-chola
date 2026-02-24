# AI-OPS-116 - Sanction Data Catalog Lane (Sources + Typologies + Procedural KPI Contract)

Date: 2026-02-23

## Scope

Next TODO batch delivered for sanctions lanes:

- Source pilot catalog for sanction volume (5 organism lanes).
- Cross-domain infraction typology catalog with initial mappings to norm fragments.
- Procedural justice KPI definition contract (`recurso`, annulment, delay).

## What Shipped

- Schema additions in `etl/load/sqlite_schema.sql`:
  - `sanction_volume_sources`
  - `sanction_infraction_types`
  - `sanction_infraction_type_mappings`
  - `sanction_volume_observations`
  - `sanction_procedural_kpi_definitions`
  - `sanction_procedural_metrics`
- New seed:
  - `etl/data/seeds/sanction_data_catalog_seed_v1.json`
- New scripts:
  - `scripts/validate_sanction_data_catalog_seed.py`
  - `scripts/import_sanction_data_catalog_seed.py`
  - `scripts/report_sanction_data_catalog_status.py`
- New tests:
  - `tests/test_validate_sanction_data_catalog_seed.py`
  - `tests/test_import_sanction_data_catalog_seed.py`
  - `tests/test_report_sanction_data_catalog_status.py`
- New `just` lanes:
  - `parl-validate-sanction-data-catalog-seed`
  - `parl-import-sanction-data-catalog-seed`
  - `parl-report-sanction-data-catalog-status`
  - `parl-sanction-data-catalog-pipeline`
  - `parl-sanction-foundation-pipeline`
  - `parl-test-sanction-data-catalog`

## Evidence

- End-to-end foundation pipeline (`norms + data catalog`) on fresh DB:
  - `docs/etl/sprints/AI-OPS-116/evidence/just_parl_sanction_foundation_pipeline_20260223T174656Z.txt`
- Seed validation:
  - `docs/etl/sprints/AI-OPS-116/evidence/sanction_data_catalog_validate_20260223T174656Z.json`
  - Result: `valid=true`, `volume_sources_total=5`, `infraction_types_total=10`, `infraction_mappings_total=10`, `procedural_kpis_total=3`
- Seed import:
  - `docs/etl/sprints/AI-OPS-116/evidence/sanction_data_catalog_import_20260223T174656Z.json`
  - Result: inserted `5 volume_sources`, `10 infraction_types`, `10 mappings`, `3 procedural_kpis`, unresolved refs `0/0`
- Status report:
  - `docs/etl/sprints/AI-OPS-116/evidence/sanction_data_catalog_status_20260223T174656Z.json`
  - Result: `status=ok`, mapping coverage `fragment=0.8`, `norm=0.8`, seed checks green
- Tests:
  - `docs/etl/sprints/AI-OPS-116/evidence/just_parl_test_sanction_data_catalog_20260223T174656Z.txt`
  - `docs/etl/sprints/AI-OPS-116/evidence/just_parl_test_sanction_norms_seed_20260223T174656Z.txt`
  - Result: `OK`
- Integrity:
  - `docs/etl/sprints/AI-OPS-116/evidence/sqlite_fk_check_20260223T174656Z.txt`
  - Result: empty output (`PRAGMA foreign_key_check` clean)

## Where We Are Now

- We have a reproducible sanctions data contract with:
  - source lanes (`who publishes sanction volume`),
  - infraction taxonomy (`what gets sanctioned`),
  - first mapping layer to norm fragments (`why under which legal basis`),
  - procedural KPI definitions (`is enforcement fair/procedural`).
- This enables controlled connector work without redefining schema each sprint.

## Where We Are Going

- Start loading real volume observations by source and period into `sanction_volume_observations`.
- Add procedural outcome observations into `sanction_procedural_metrics`.
- Expand municipal mappings from source-only to normalized ordinance fragments.

## Next

- Build first connector slice for one state source (recommended: DGT) and load first real `expediente/importe` observations.
- Build municipal ordinance normalizer pilot (`20 cities`) to replace source-only municipal mappings with `norm_fragment_id`.
- Publish first `top_normas_sancion_ciudadana` draft once observation rows exist.
