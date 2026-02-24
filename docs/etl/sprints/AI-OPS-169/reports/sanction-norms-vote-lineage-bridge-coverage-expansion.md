# AI-OPS-169 - Sanction Norms Vote Lineage Bridge Coverage Expansion

Date: 2026-02-24

## Objective
Raise parliamentary/vote responsibility coverage in Scenario A (`Derechos`) without adding new upstream dependencies.

## What changed
- Extended `scripts/backfill_sanction_norms_vote_evidence.py` with conservative lineage bridges:
  - `lineage_target_to_vote_norm:desarrolla|modifica`
  - `lineage_shared_deroga_related_norm`
- Added bridge metadata to vote evidence payloads:
  - `candidate_boe_id`, `bridge_kind`, `bridge_from_boe_id`, `bridge_anchor_related_boe_id`, `bridge_anchor_related_norm_id`
- Added regression test in `tests/test_backfill_sanction_norms_vote_evidence.py` for lineage bridge insertion.

## Reproducible run
- Parliamentary refresh:
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_ROLES=approve,propose,enforce,delegate just parl-backfill-sanction-norms-parliamentary-evidence`
- Vote backfill with lineage bridge logic:
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_VOTE_EVIDENCE_ROLES=approve,propose,enforce,delegate just parl-backfill-sanction-norms-vote-evidence`
- Status + queue + integrity:
  - `DB_PATH=etl/data/staging/politicos-es.db just parl-report-sanction-norms-seed-status`
  - `DB_PATH=etl/data/staging/politicos-es.db just parl-export-sanction-norms-seed-source-record-upgrade-queue`
  - `sqlite3 etl/data/staging/politicos-es.db 'PRAGMA foreign_key_check;'`
- Tests:
  - `just parl-test-sanction-norms-seed`
  - `just parl-test-liberty-restrictions`

## Result
Coverage deltas vs AI-OPS-168:
- `responsibility_evidence_items_total`: `78 -> 95` (`+17`)
- `responsibility_evidence_items_parliamentary_total`: `27 -> 44` (`+17`)
- `responsibility_evidence_items_parliamentary_vote_total`: `25 -> 42` (`+17`)
- `responsibilities_with_parliamentary_evidence_total`: `9/15 -> 11/15` (`0.60 -> 0.733333`)
- `responsibilities_with_parliamentary_vote_evidence_total`: `7/15 -> 11/15` (`0.466667 -> 0.733333`)
- `responsibilities_with_execution_evidence_total`: remains `15/15`
- `queue_rows_total`: remains `0`
- `fk_violations_total`: remains `0`

Backfill stats (AI-OPS-169):
- Parliamentary backfill: `candidate_matches_total=2`, `evidence_inserted=0`, `evidence_updated=2`
- Vote backfill: `candidate_matches_total=69`, `evidence_inserted=17`, `evidence_updated=102`
- New bridge match methods observed:
  - `title_rule:ley_58_2003_general_tributaria+lineage_target_to_vote_norm:desarrolla`
  - `title_rule:...seguridad_ciudadana+lineage_shared_deroga_related_norm`

## Remaining gap
Still missing parliamentary/vote evidence on 4 responsibilities:
- `BOE-A-1994-8985` (`delegate`, `enforce`)
- `BOE-A-2000-15060` (`approve`, `enforce`)

These remain `0/2` and `0/2` respectively in vote/parliamentary coverage.

## Evidence
- `docs/etl/sprints/AI-OPS-169/evidence/sanction_norms_parliamentary_evidence_backfill_20260224T092206Z.json`
- `docs/etl/sprints/AI-OPS-169/evidence/sanction_norms_vote_evidence_backfill_20260224T092206Z.json`
- `docs/etl/sprints/AI-OPS-169/evidence/sanction_norms_seed_status_20260224T092206Z.json`
- `docs/etl/sprints/AI-OPS-169/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T092206Z.json`
- `docs/etl/sprints/AI-OPS-169/evidence/sqlite_fk_check_20260224T092206Z.txt`
- `docs/etl/sprints/AI-OPS-169/evidence/just_parl_test_sanction_norms_seed_20260224T092206Z.txt`
- `docs/etl/sprints/AI-OPS-169/evidence/just_parl_test_liberty_restrictions_20260224T092206Z.txt`
