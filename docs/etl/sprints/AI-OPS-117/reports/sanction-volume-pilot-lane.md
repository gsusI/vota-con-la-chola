# AI-OPS-117 - Sanction Volume Pilot Lane (Top-N + Dossiers + Municipal Pilot 20)

Date: 2026-02-23

## Scope

Next TODO batch delivered for sanctions/citizen lanes:

- `top_normas_sancion_ciudadana` with reproducible ranking over `sanction_volume_observations`.
- `dossiers` per norm with legal drill-down (`norma -> fragmento`) and source lanes.
- Municipal pilot progress model (`20 ciudades`) for sanctioning ordinances and normalized fragments.

## What Shipped

- Schema additions in `etl/load/sqlite_schema.sql`:
  - `sanction_municipal_ordinances`
  - `sanction_municipal_ordinance_fragments`
- New seed:
  - `etl/data/seeds/sanction_volume_pilot_seed_v1.json`
- New scripts:
  - `scripts/validate_sanction_volume_pilot_seed.py`
  - `scripts/import_sanction_volume_pilot_seed.py`
  - `scripts/report_sanction_volume_pilot_status.py`
- New tests:
  - `tests/test_validate_sanction_volume_pilot_seed.py`
  - `tests/test_import_sanction_volume_pilot_seed.py`
  - `tests/test_report_sanction_volume_pilot_status.py`
- New `just` lanes:
  - `parl-validate-sanction-volume-pilot-seed`
  - `parl-import-sanction-volume-pilot-seed`
  - `parl-report-sanction-volume-pilot-status`
  - `parl-sanction-volume-pilot-pipeline`
  - `parl-sanction-citizen-pilot-pipeline`
  - `parl-test-sanction-volume-pilot`
- Reliability fix:
  - sanction lanes now run scripts with `PYTHONPATH=.` in `justfile` to avoid `ModuleNotFoundError: etl` when invoked outside unittest context.

## Evidence

- End-to-end sanctions citizen pilot pipeline on clean DB:
  - `docs/etl/sprints/AI-OPS-117/evidence/just_parl_sanction_citizen_pilot_pipeline_20260223T180041Z.txt`
- Pilot seed validation:
  - `docs/etl/sprints/AI-OPS-117/evidence/sanction_volume_pilot_validate_20260223T180041Z.json`
  - Result: `valid=true`
- Pilot seed import:
  - `docs/etl/sprints/AI-OPS-117/evidence/sanction_volume_pilot_import_20260223T180041Z.json`
  - Result: inserted `9` observations, `6` procedural metrics, `20` municipal ordinances, `3` municipal fragments; unresolved refs `0`
- Pilot status report:
  - `docs/etl/sprints/AI-OPS-117/evidence/sanction_volume_pilot_status_20260223T180041Z.json`
  - Result: `status=ok`, `top_norms_total=6`, `norm_dossiers_total=5`, `observations_with_norm_pct=0.777778`
  - Municipal result: `ordinances_total=20`, `normalized_total=3`, `identified_total=17`, `mapped_fragment_total=2`
- Regression tests:
  - `docs/etl/sprints/AI-OPS-117/evidence/just_parl_test_sanction_norms_seed_20260223T180041Z.txt`
  - `docs/etl/sprints/AI-OPS-117/evidence/just_parl_test_sanction_data_catalog_20260223T180041Z.txt`
  - `docs/etl/sprints/AI-OPS-117/evidence/just_parl_test_sanction_volume_pilot_20260223T180041Z.txt`
  - Result: `OK`
- Integrity:
  - `docs/etl/sprints/AI-OPS-117/evidence/sqlite_fk_check_20260223T180041Z.txt`
  - Result: empty output (`PRAGMA foreign_key_check` clean)

## Where We Are Now

- `top_normas_sancion_ciudadana` is operational over pilot data with reproducible methodology:
  - primary sort `expediente_count`, secondary `importe_total_eur`
  - explicit incidence proxy `incidence_per_1000_observed_cases`
- Dossiers are available with direct audit links to legal fragments and source lanes.
- Municipal pilot 20-city catalog is seeded and partially normalized (`3/20`, `15%`).

## Where We Are Going

- Replace pilot values with real ingested series by source and territory.
- Add population denominators to move from incidence proxy to `incidencia por 1.000 habitantes`.
- Expand municipal normalization from `3` to `20` ordinances with comparable `articulo/conducta/rango/recurso`.

## Next

- Run source-specific ingestion slices (DGT/AEAT/TGSS/Interior/municipal) into `sanction_volume_observations`.
- Backfill territorial keys/population reference for per-1,000-citizen incidence.
- Raise municipal mapping coverage (`mapped_fragment_id`) before moving rows 77/78/82 beyond `PARTIAL`.
