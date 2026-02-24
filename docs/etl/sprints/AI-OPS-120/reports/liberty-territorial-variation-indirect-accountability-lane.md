# AI-OPS-120 - Liberty Territorial Variation + Indirect Accountability Lane

Date: 2026-02-23

## Scope

Next TODO batch delivered in active `Derechos` focus:

- Start measurable territorial variation lane for enforcement arbitrariness by `fragment_id`.
- Start second-order indirect accountability lane with explicit `causal_distance` and `edge_confidence`.
- Keep atlas snapshot user-facing by exporting both new lanes in the same artifact.

## What Shipped

- Schema additions in `etl/load/sqlite_schema.sql`:
  - `liberty_enforcement_methodologies`
  - `liberty_enforcement_observations`
  - `liberty_indirect_methodologies`
  - `liberty_indirect_responsibility_edges`
  - indexes for enforcement (`fragment_id`, `territory_key`, `period_date`) and indirect (`fragment_id`, `role`, `edge_confidence`, `causal_distance`)
- New seeds:
  - `etl/data/seeds/liberty_enforcement_seed_v1.json`
  - `etl/data/seeds/liberty_indirect_accountability_seed_v1.json`
- New scripts:
  - `scripts/validate_liberty_enforcement_seed.py`
  - `scripts/import_liberty_enforcement_seed.py`
  - `scripts/report_liberty_enforcement_variation_status.py`
  - `scripts/validate_liberty_indirect_accountability_seed.py`
  - `scripts/import_liberty_indirect_accountability_seed.py`
  - `scripts/report_liberty_indirect_accountability_status.py`
- `just` lanes added:
  - `parl-validate/import/report/check-liberty-enforcement-*`
  - `parl-validate/import/report/check-liberty-indirect-accountability-*`
- Snapshot extension:
  - `scripts/export_liberty_restrictions_snapshot.py` now includes `enforcement_variation`, `indirect_accountability_edges`, `indirect_accountability_summary`.
- Tests added:
  - `tests/test_validate_liberty_enforcement_seed.py`
  - `tests/test_import_liberty_enforcement_seed.py`
  - `tests/test_report_liberty_enforcement_variation_status.py`
  - `tests/test_validate_liberty_indirect_accountability_seed.py`
  - `tests/test_import_liberty_indirect_accountability_seed.py`
  - `tests/test_report_liberty_indirect_accountability_status.py`
  - updated `tests/test_export_liberty_restrictions_snapshot.py`

## Evidence

- End-to-end pipeline with all liberty lanes on clean DB:
  - `docs/etl/sprints/AI-OPS-120/evidence/just_parl_liberty_restrictions_pipeline_20260223T183508Z.txt`
- Territorial variation seed validation/import/status:
  - `docs/etl/sprints/AI-OPS-120/evidence/liberty_enforcement_validate_20260223T183508Z.json`
  - `docs/etl/sprints/AI-OPS-120/evidence/liberty_enforcement_import_20260223T183508Z.json`
  - `docs/etl/sprints/AI-OPS-120/evidence/liberty_enforcement_status_20260223T183508Z.json`
  - Result: `status=ok`, `observations_total=16`, `fragments_with_multi_territory_total=8/8`, `high_variation_fragments_total=3`, `gate.passed=true`.
- Indirect chain seed validation/import/status:
  - `docs/etl/sprints/AI-OPS-120/evidence/liberty_indirect_validate_20260223T183508Z.json`
  - `docs/etl/sprints/AI-OPS-120/evidence/liberty_indirect_import_20260223T183508Z.json`
  - `docs/etl/sprints/AI-OPS-120/evidence/liberty_indirect_status_20260223T183508Z.json`
  - Result: `status=ok`, `edges_total=12`, `attributable_edges_total=9`, `fragments_with_attributable_edges_total=7/8`, `high_confidence_far_edges_total=0`, `gate.passed=true`.
- Snapshot export:
  - `docs/etl/sprints/AI-OPS-120/exports/liberty_restrictions_snapshot_20260223T183508Z.json`
  - Result totals include `enforcement_observations_total=16`, `indirect_edges_total=12`, `indirect_attributable_edges_total=9`.
- Tests:
  - `docs/etl/sprints/AI-OPS-120/evidence/just_parl_test_liberty_restrictions_20260223T183508Z.txt`
  - Result: `Ran 23 tests ... OK`.
- Integrity:
  - `docs/etl/sprints/AI-OPS-120/evidence/sqlite_fk_check_20260223T183508Z.txt`
  - Result: empty output (`PRAGMA foreign_key_check` clean).

## Where We Are Now

- Row 99 now has measurable, reproducible territorial dispersion metrics (`sanciones_per_1000`, `% anulacion`, `delay p90`) per fragment and a gate-backed status output.
- Row 102 now has a machine-readable second-order chain with explicit causal filters (`confidence`, `distance`) and anti-over-attribution check.
- Atlas snapshot now ships direct + proportionality + territorial + indirect views together.

## Where We Are Going

- Replace seed observations with periodic ingestion by territory/source and extend beyond current pilot territories.
- Connect indirect edges to person/cargo and appointment evidence timelines.
- Add stronger anti-over-attribution controls tied to appointment validity windows and conflict rules.

## Next

- Ingest real territorial series for sanctions/resources/plazos into `liberty_enforcement_observations` refreshes.
- Add person/cargo FK enrichment for indirect edges (`appoint/instruct/design`) with date-valid role windows.
- Tighten gates with minimum territorial breadth and stricter attribution confidence thresholds once ingestion coverage grows.
