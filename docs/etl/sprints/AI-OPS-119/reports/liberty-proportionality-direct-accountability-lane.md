# AI-OPS-119 - Liberty Proportionality + Direct Accountability Lane

Date: 2026-02-23

## Scope

Next TODO batch delivered in active `Derechos` focus:

- Add reproducible proportionality/necessity review per restrictive fragment.
- Start direct responsibility chain coverage by `fragment_id`.
- Publish auditable actor-level `responsibility_score` (direct + indirect weighted edges).
- Extend atlas snapshot with proportionality and accountability score payloads.

## What Shipped

- Schema additions in `etl/load/sqlite_schema.sql`:
  - `liberty_proportionality_methodologies`
  - `liberty_proportionality_reviews`
  - indexes for `fragment_id`, `assessment_label`, `proportionality_score`
- New seed:
  - `etl/data/seeds/liberty_proportionality_seed_v1.json`
- New scripts:
  - `scripts/validate_liberty_proportionality_seed.py`
  - `scripts/import_liberty_proportionality_seed.py`
  - `scripts/report_liberty_proportionality_status.py`
  - `scripts/report_liberty_direct_accountability_scores.py`
- Snapshot export extension:
  - `scripts/export_liberty_restrictions_snapshot.py` now includes `proportionality_reviews`, `accountability_scores`, `accountability_methodology`
- New tests:
  - `tests/test_validate_liberty_proportionality_seed.py`
  - `tests/test_import_liberty_proportionality_seed.py`
  - `tests/test_report_liberty_proportionality_status.py`
  - `tests/test_report_liberty_direct_accountability_scores.py`
  - updated `tests/test_export_liberty_restrictions_snapshot.py`
- New `just` lanes:
  - `parl-validate-liberty-proportionality-seed`
  - `parl-import-liberty-proportionality-seed`
  - `parl-report-liberty-proportionality-status`
  - `parl-check-liberty-proportionality-gate`
  - `parl-report-liberty-direct-accountability-scores`
  - `parl-check-liberty-direct-accountability-gate`

## Evidence

- End-to-end liberty pipeline on clean DB:
  - `docs/etl/sprints/AI-OPS-119/evidence/just_parl_liberty_restrictions_pipeline_20260223T182117Z.txt`
- Proportionality seed validation:
  - `docs/etl/sprints/AI-OPS-119/evidence/liberty_proportionality_validate_20260223T182117Z.json`
  - Result: `valid=true`, `reviews_total=8`
- Proportionality import:
  - `docs/etl/sprints/AI-OPS-119/evidence/liberty_proportionality_import_20260223T182117Z.json`
  - Result: inserted `1` methodology, `8` reviews, unresolved fragment refs `0`
- Proportionality status + gate:
  - `docs/etl/sprints/AI-OPS-119/evidence/liberty_proportionality_status_20260223T182117Z.json`
  - Result: `status=ok`, `target_fragments_coverage_pct=1.0`, `objective_defined_pct=1.0`, `indicator_defined_pct=0.75`, `alternatives_considered_pct=0.5`, `gate.passed=true`
  - Low-score sample captured (`2` reviews below threshold) for review prioritization.
- Direct accountability scoring:
  - `docs/etl/sprints/AI-OPS-119/evidence/liberty_direct_accountability_scores_20260223T182117Z.json`
  - Result: `status=ok`, `fragments_with_direct_chain_total=8/8`, `direct_edges_total=13`, `actors_scored_total=8`, `gate.passed=true`
- Snapshot export:
  - `docs/etl/sprints/AI-OPS-119/exports/liberty_restrictions_snapshot_20260223T182117Z.json`
  - Result: `restrictions_total=8`, `accountability_edges_total=15`, `proportionality_reviews_total=8`, `actors_scored_total=8`
- Tests:
  - `docs/etl/sprints/AI-OPS-119/evidence/just_parl_test_liberty_restrictions_20260223T182259Z.txt`
  - Result: `Ran 13 tests ... OK`
- Integrity:
  - `docs/etl/sprints/AI-OPS-119/evidence/sqlite_fk_check_20260223T182259Z.txt`
  - Result: empty output (`PRAGMA foreign_key_check` clean)

## Where We Are Now

- Tracker row 98 now has a reproducible proportionality contract and enforceable gate for seeded restrictions.
- Tracker row 101 has initial direct-chain coverage (`propose/approve/enforce`) over all seeded fragments.
- Tracker row 103 has actor-level scoring with explicit role weights and formula for auditability.
- Atlas snapshot now carries both legal restriction evidence and attribution/proportionality outputs in one artifact.

## Where We Are Going

- Replace seed-only proportionality fields with ingestion-backed evidence from AIR/memorias/ex-post evaluations.
- Extend direct chain beyond seed responsibilities into vote/sign/resolve evidence with temporal validation.
- Add indirect-causal attribution lanes (`appoint/instruct/design`) with confidence and anti-over-attribution rules.

## Next

- Add ingestion slices for proportionality evidence sources and connect them to `liberty_proportionality_reviews` refreshes.
- Enrich direct responsibility edges with date/source_quote provenance fields.
- Expand the scoring model from institution-level actors to person/cargo entities where evidence is primary and timestamped.
