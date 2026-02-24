# AI-OPS-115 - Sanction Norms Seed Lane (Normative + Accountability Base)

Date: 2026-02-23

## Scope

Controllable slice delivered for the next TODO batch in `tracker + roadmap-tecnico`:

- Add normative fragment model and accountability edges in SQLite:
  - `legal_norms`
  - `legal_norm_fragments`
  - `legal_fragment_responsibilities`
  - `sanction_norm_catalog`
  - `sanction_norm_fragment_links`
- Publish initial sanction norms seed contract:
  - `etl/data/seeds/sanction_norms_seed_v1.json`
- Add operational scripts:
  - `scripts/validate_sanction_norms_seed.py`
  - `scripts/import_sanction_norms_seed.py`
  - `scripts/report_sanction_norms_seed_status.py`
- Add `just` reproducible lane:
  - `parl-validate-sanction-norms-seed`
  - `parl-import-sanction-norms-seed`
  - `parl-report-sanction-norms-seed-status`
  - `parl-sanction-norms-seed-pipeline`
  - `parl-test-sanction-norms-seed`
- Add tests:
  - `tests/test_validate_sanction_norms_seed.py`
  - `tests/test_import_sanction_norms_seed.py`
  - `tests/test_report_sanction_norms_seed_status.py`

## Evidence

Primary run artifacts:

- Validate seed:
  - `docs/etl/sprints/AI-OPS-115/evidence/sanction_norms_seed_validate_20260223T173448Z.json`
  - Result: `valid=true`, `norms_total=8`, `fragments_total=8`, `responsibility_hints_total=15`
- Import seed into fresh SQLite:
  - `docs/etl/sprints/AI-OPS-115/evidence/sanction_norms_seed_import_20260223T173448Z.json`
  - Result: inserted `8 norms`, `8 catalog rows`, `8 fragments`, `8 links`, `15 responsibilities`
- Status report:
  - `docs/etl/sprints/AI-OPS-115/evidence/sanction_norms_seed_status_20260223T173448Z.json`
  - Result: `status=ok`, `responsibility_coverage_pct=1.0`
- FK integrity:
  - `docs/etl/sprints/AI-OPS-115/evidence/sqlite_fk_check_20260223T173448Z.txt`
  - Result: empty output (`PRAGMA foreign_key_check` clean)
- Repro lane via just:
  - `docs/etl/sprints/AI-OPS-115/evidence/just_parl_sanction_norms_seed_pipeline_20260223T173646Z.txt`
- Tests:
  - `docs/etl/sprints/AI-OPS-115/evidence/just_parl_test_sanction_norms_seed_20260223T173633Z.txt`
  - Result: `Ran 5 tests ... OK`

## Where We Are Now

- The seed and schema foundation for normative fragments and sanction accountability is operational.
- We can reproducibly validate, import, and report lane health in one command path.
- Initial closed set (8 BOE norms) is loaded and traceable in DB tables.

## Where We Are Going

- Expand from seed-level single fragment per norm into full fragment coverage (article/disposition/annex) and legal change lineage.
- Replace hint-only accountability with evidence-backed role edges from Congreso/Senado/BOE records.
- Move from normative base to comparable sanction volume datasets by organism/territory.

## Next

- Build `v2` backfill for multi-fragment extraction per BOE norm (`fragment_id` stability + lineage).
- Add edge-level fields for dated legal citations (`evidence_date`, `evidence_quote`) from primary records.
- Open first sanction-volume ingestion lane (DGT/AEAT/TGSS/Interior/municipal pilots) keyed to `norma_fragmento_id`.
