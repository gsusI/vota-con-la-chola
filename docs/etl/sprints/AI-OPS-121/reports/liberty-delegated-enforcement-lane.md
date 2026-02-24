# AI-OPS-121 - Liberty Delegated Enforcement Lane

Date: 2026-02-23

## Scope

Next TODO batch delivered in active `Derechos` focus:

- Start delegated enforcement accountability lane for row 67 (`norma_habilitante -> organismo -> cargo designado -> acto de enforcement`).
- Keep the lane reproducible with seed + validate/import/report scripts and explicit gate thresholds.
- Extend the same public liberty snapshot with delegated-chain outputs.

## What Shipped

- Schema additions in `etl/load/sqlite_schema.sql`:
  - `liberty_delegated_enforcement_methodologies`
  - `liberty_delegated_enforcement_links`
  - indexes on `fragment_id`, delegated institution, designated actor, and confidence
- New seed:
  - `etl/data/seeds/liberty_delegated_enforcement_seed_v1.json`
- New scripts:
  - `scripts/validate_liberty_delegated_enforcement_seed.py`
  - `scripts/import_liberty_delegated_enforcement_seed.py`
  - `scripts/report_liberty_delegated_enforcement_status.py`
- `just` lanes added:
  - `parl-validate/import/report/check-liberty-delegated-enforcement-*`
- Snapshot extension:
  - `scripts/export_liberty_restrictions_snapshot.py` now includes `delegated_enforcement_links` and `delegated_enforcement_summary`.
- Tests added:
  - `tests/test_validate_liberty_delegated_enforcement_seed.py`
  - `tests/test_import_liberty_delegated_enforcement_seed.py`
  - `tests/test_report_liberty_delegated_enforcement_status.py`
  - updated `tests/test_export_liberty_restrictions_snapshot.py`

## Evidence

- End-to-end pipeline with all liberty lanes on clean DB:
  - `docs/etl/sprints/AI-OPS-121/evidence/just_parl_liberty_restrictions_pipeline_20260223T184315Z.txt`
- Delegated lane validate/import/status:
  - `docs/etl/sprints/AI-OPS-121/evidence/liberty_delegated_validate_20260223T184315Z.json`
  - `docs/etl/sprints/AI-OPS-121/evidence/liberty_delegated_import_20260223T184315Z.json`
  - `docs/etl/sprints/AI-OPS-121/evidence/liberty_delegated_status_20260223T184315Z.json`
  - Result: `status=ok`, `links_total=8`, `fragments_with_links_total=8/8`, `fragments_with_designated_actor_total=6`, `links_with_enforcement_evidence_total=7`, `weak_links_total=2`, `gate.passed=true`.
- Snapshot export:
  - `docs/etl/sprints/AI-OPS-121/exports/liberty_restrictions_snapshot_20260223T184315Z.json`
  - Result totals include `delegated_links_total=8`, `fragments_with_delegated_chain_total=8`.
- Tests:
  - `docs/etl/sprints/AI-OPS-121/evidence/just_parl_test_liberty_restrictions_20260223T184315Z.txt`
  - Result: `Ran 28 tests ... OK`.
- Integrity:
  - `docs/etl/sprints/AI-OPS-121/evidence/sqlite_fk_check_20260223T184315Z.txt`
  - Result: empty output (`PRAGMA foreign_key_check` clean).

## Where We Are Now

- Row 67 is no longer TODO-only: there is now a machine-readable delegated-chain lane with designated actor and enforcement evidence coverage metrics.
- The liberty atlas snapshot now includes direct + proportionality + territorial + indirect + delegated views in one artifact.

## Where We Are Going

- Replace seed-only delegated chains with primary-source ingestion for appointments and enforcement acts by organism.
- Add person/cargo resolution and validity windows (`appointment_start/end`) to harden attribution.
- Reduce weak links (`missing designated actor` or `missing enforcement evidence`) until gate thresholds can be tightened.

## Next

- Ingest appointment evidence and enforcement acts per organism (DGT/AEAT/ITSS/Delegaciones) with dated primary links.
- Promote delegated links from institution-level placeholders to person/cargo-level edges.
- Add stricter gates (designated actor and enforcement evidence coverage) after first real-data refresh.
