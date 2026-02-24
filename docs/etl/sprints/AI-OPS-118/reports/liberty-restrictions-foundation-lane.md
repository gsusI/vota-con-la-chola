# AI-OPS-118 - Liberty Restrictions Foundation Lane (IRLC + Rights Map + Focus Gate)

Date: 2026-02-23

## Scope

Next TODO batch delivered in the active `Derechos` focus:

- IRLC methodology and scoring model by `fragment_id`.
- Restriction map by affected right (`movilidad`, `actividad_economica`, `expresion_reunion`, etc.).
- Coverage KPIs + enforceable focus gate for rights lanes.
- First snapshot artifact for the Restrictions Atlas.

## What Shipped

- Schema additions in `etl/load/sqlite_schema.sql`:
  - `liberty_irlc_methodologies`
  - `liberty_right_categories`
  - `liberty_restriction_assessments`
  - indexes for fragment/right/score lookups
- New seed:
  - `etl/data/seeds/liberty_restrictions_seed_v1.json`
- New scripts:
  - `scripts/validate_liberty_restrictions_seed.py`
  - `scripts/import_liberty_restrictions_seed.py`
  - `scripts/report_liberty_restrictions_status.py`
  - `scripts/export_liberty_restrictions_snapshot.py`
- New tests:
  - `tests/test_validate_liberty_restrictions_seed.py`
  - `tests/test_import_liberty_restrictions_seed.py`
  - `tests/test_report_liberty_restrictions_status.py`
  - `tests/test_export_liberty_restrictions_snapshot.py`
- New `just` lanes:
  - `parl-validate-liberty-restrictions-seed`
  - `parl-import-liberty-restrictions-seed`
  - `parl-report-liberty-restrictions-status`
  - `parl-check-liberty-focus-gate`
  - `parl-export-liberty-restrictions-snapshot`
  - `parl-liberty-restrictions-pipeline`
  - `parl-test-liberty-restrictions`

## Evidence

- End-to-end liberty pipeline on clean DB:
  - `docs/etl/sprints/AI-OPS-118/evidence/just_parl_liberty_restrictions_pipeline_20260223T181035Z.txt`
- Seed validation:
  - `docs/etl/sprints/AI-OPS-118/evidence/liberty_restrictions_validate_20260223T181035Z.json`
  - Result: `valid=true`
- Seed import:
  - `docs/etl/sprints/AI-OPS-118/evidence/liberty_restrictions_import_20260223T181035Z.json`
  - Result: inserted `1` methodology, `6` right categories, `8` assessments; unresolved refs `0`
- Status + gate:
  - `docs/etl/sprints/AI-OPS-118/evidence/liberty_restrictions_status_20260223T181035Z.json`
  - Result: `status=ok`, `norms_classified_pct=1.0`, `fragments_with_irlc_pct=1.0`, `fragments_with_accountability_pct=1.0`, `focus_gate.passed=true`
- Snapshot export:
  - `docs/etl/sprints/AI-OPS-118/exports/liberty_restrictions_snapshot_20260223T181035Z.json`
  - Result: `restrictions_total=8`, `accountability_edges_total=15`
- Tests:
  - `docs/etl/sprints/AI-OPS-118/evidence/just_parl_test_liberty_restrictions_20260223T181035Z.txt`
  - Result: `OK`
- Integrity:
  - `docs/etl/sprints/AI-OPS-118/evidence/sqlite_fk_check_20260223T181035Z.txt`
  - Result: empty output (`PRAGMA foreign_key_check` clean)

## Where We Are Now

- The rights lane now has a reproducible IRLC contract (`method_version`, explicit weights, auditable component scores).
- A machine-readable rights map is available by category with top restrictions and legal drill-down.
- Focus gate is executable (`--enforce-gate`) and currently green for the seeded scope.
- First atlas artifact exists as JSON snapshot with restrictions + accountability edges.

## Where We Are Going

- Expand from seeded sanctions fragments to broader rights-restrictive universe (Estado + CCAA + municipal).
- Replace seed-only assessments with ingestion-backed evidence and versioned refresh routines.
- Add periodic snapshot diffs and published artifacts aligned with tracker row 105 requirements.

## Next

- Build connector slices for restrictions inventory beyond current sanction catalog.
- Add scheduled snapshot export + changelog and expose it in published artifacts.
- Extend mapping coverage to underrepresented right categories (`privacidad`, `acceso_servicios`, `propiedad_uso`).
