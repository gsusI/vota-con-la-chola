# AI-OPS-170 - Sanction Norms Vote Mixed-Lineage Bridge Closure

Date: 2026-02-24

## Objective
Continue Scenario A (`Derechos`) by raising parliamentary/vote responsibility coverage with controllable in-repo logic only.

## What changed
- Extended `scripts/backfill_sanction_norms_vote_evidence.py` with a conservative mixed-lineage bridge:
  - `lineage_shared_related_norm_mixed_relation` (shared anchor where one side is `deroga` and the other is `desarrolla|modifica`)
- Added regression coverage in `tests/test_backfill_sanction_norms_vote_evidence.py`:
  - `test_backfill_bridges_vote_evidence_via_mixed_lineage_anchor`
- Re-ran the full sanction-norms evidence bundle on `etl/data/staging/politicos-es.db`.

## Reproducible run
- Parliamentary refresh:
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_ROLES=approve,propose,enforce,delegate SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_OUT=docs/etl/sprints/AI-OPS-170/evidence/sanction_norms_parliamentary_evidence_backfill_20260224T093142Z.json just parl-backfill-sanction-norms-parliamentary-evidence`
- Vote backfill with mixed bridge:
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_VOTE_EVIDENCE_ROLES=approve,propose,enforce,delegate SANCTION_NORMS_VOTE_EVIDENCE_OUT=docs/etl/sprints/AI-OPS-170/evidence/sanction_norms_vote_evidence_backfill_20260224T093142Z.json just parl-backfill-sanction-norms-vote-evidence`
- Status + queue + integrity:
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_SEED_STATUS_OUT=docs/etl/sprints/AI-OPS-170/evidence/sanction_norms_seed_status_20260224T093142Z.json just parl-report-sanction-norms-seed-status`
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_OUT=docs/etl/sprints/AI-OPS-170/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T093142Z.json SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_CSV_OUT=docs/etl/sprints/AI-OPS-170/exports/sanction_norms_seed_source_record_upgrade_queue_20260224T093142Z.csv just parl-export-sanction-norms-seed-source-record-upgrade-queue`
  - `sqlite3 etl/data/staging/politicos-es.db 'PRAGMA foreign_key_check;'`
  - `sqlite3 -header -csv etl/data/staging/politicos-es.db "WITH base AS (SELECT r.responsibility_id, ln.boe_id, r.role FROM legal_fragment_responsibilities r JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id JOIN sanction_norm_catalog c ON c.norm_id = l.norm_id JOIN legal_norms ln ON ln.norm_id = c.norm_id), flags AS (SELECT b.*, EXISTS(SELECT 1 FROM legal_fragment_responsibility_evidence e WHERE e.responsibility_id=b.responsibility_id AND e.evidence_type IN ('congreso_diario','senado_diario','congreso_vote','senado_vote')) AS has_parliamentary_any, EXISTS(SELECT 1 FROM legal_fragment_responsibility_evidence e WHERE e.responsibility_id=b.responsibility_id AND e.evidence_type IN ('congreso_vote','senado_vote')) AS has_vote FROM base b) SELECT * FROM flags WHERE has_parliamentary_any=0 OR has_vote=0 ORDER BY boe_id, role;" > docs/etl/sprints/AI-OPS-170/evidence/responsibility_parliamentary_vote_gap_20260224T093142Z.csv`
- Tests:
  - `just parl-test-sanction-norms-seed`
  - `just parl-test-liberty-restrictions`

## Result
Coverage deltas vs AI-OPS-169:
- `responsibility_evidence_items_total`: `95 -> 97` (`+2`)
- `responsibility_evidence_items_parliamentary_total`: `44 -> 46` (`+2`)
- `responsibility_evidence_items_parliamentary_vote_total`: `42 -> 44` (`+2`)
- `responsibilities_with_parliamentary_evidence_total`: `11/15 -> 13/15` (`0.733333 -> 0.866667`)
- `responsibilities_with_parliamentary_vote_evidence_total`: `11/15 -> 13/15` (`0.733333 -> 0.866667`)
- `responsibilities_with_execution_evidence_total`: remains `15/15`
- `queue_rows_total`: remains `0`
- `fk_violations_total`: remains `0`

Backfill stats (AI-OPS-170):
- Parliamentary backfill: `candidate_matches_total=2`, `evidence_inserted=0`, `evidence_updated=2`
- Vote backfill: `candidate_matches_total=71`, `evidence_inserted=2`, `evidence_updated=121`
- New method observed in production run:
  - `title_rule:rdl_6_2015_trafico_seguridad_vial+lineage_shared_related_norm_mixed_relation` (`2` matches)

## Remaining gap
Parliamentary/vote evidence now remains missing only on:
- `BOE-A-2000-15060` (`approve`, `enforce`)

`BOE-A-1994-8985` is now closed for vote coverage via mixed-lineage bridge (`has_vote=1` on both `delegate/enforce`).

## Evidence
- `docs/etl/sprints/AI-OPS-170/evidence/sanction_norms_parliamentary_evidence_backfill_20260224T093142Z.json`
- `docs/etl/sprints/AI-OPS-170/evidence/sanction_norms_vote_evidence_backfill_20260224T093142Z.json`
- `docs/etl/sprints/AI-OPS-170/evidence/sanction_norms_seed_status_20260224T093142Z.json`
- `docs/etl/sprints/AI-OPS-170/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T093142Z.json`
- `docs/etl/sprints/AI-OPS-170/evidence/responsibility_parliamentary_vote_gap_20260224T093142Z.csv`
- `docs/etl/sprints/AI-OPS-170/evidence/sqlite_fk_check_20260224T093142Z.txt`
- `docs/etl/sprints/AI-OPS-170/evidence/just_parl_test_sanction_norms_seed_20260224T093142Z.txt`
- `docs/etl/sprints/AI-OPS-170/evidence/just_parl_test_liberty_restrictions_20260224T093142Z.txt`
