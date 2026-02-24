# AI-OPS-171 - Sanction Norms Parliamentary Closure via LISOS Title Rule

Date: 2026-02-24

## Objective
Advance Scenario A by closing the remaining parliamentary coverage gap without external dependencies, using conservative in-repo matching logic.

## What changed
- Extended `scripts/backfill_sanction_norms_parliamentary_evidence.py`:
  - Added conservative title rule fallback for `BOE-A-2000-15060`:
    - `title_rule:lisos_orden_social`
  - Added observability:
    - `counts.docs_with_title_rule_match_total`
    - `by_method`
  - Preserved existing BOE-token path (`text_excerpt_boe_id_regex`) and idempotent upsert behavior.
- Added regression test:
  - `tests/test_backfill_sanction_norms_parliamentary_evidence.py::test_backfill_inserts_lisos_via_title_rule_without_boe_token`

## Reproducible run
- Parliamentary backfill:
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_ROLES=approve,propose,enforce,delegate SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_OUT=docs/etl/sprints/AI-OPS-171/evidence/sanction_norms_parliamentary_evidence_backfill_20260224T094041Z.json just parl-backfill-sanction-norms-parliamentary-evidence`
- Vote backfill (baseline refresh):
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_VOTE_EVIDENCE_ROLES=approve,propose,enforce,delegate SANCTION_NORMS_VOTE_EVIDENCE_OUT=docs/etl/sprints/AI-OPS-171/evidence/sanction_norms_vote_evidence_backfill_20260224T094041Z.json just parl-backfill-sanction-norms-vote-evidence`
- Status + queue + gap + integrity:
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_SEED_STATUS_OUT=docs/etl/sprints/AI-OPS-171/evidence/sanction_norms_seed_status_20260224T094041Z.json just parl-report-sanction-norms-seed-status`
  - `DB_PATH=etl/data/staging/politicos-es.db SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_OUT=docs/etl/sprints/AI-OPS-171/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T094041Z.json SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_CSV_OUT=docs/etl/sprints/AI-OPS-171/exports/sanction_norms_seed_source_record_upgrade_queue_20260224T094041Z.csv just parl-export-sanction-norms-seed-source-record-upgrade-queue`
  - `sqlite3 -header -csv etl/data/staging/politicos-es.db "WITH base AS (SELECT r.responsibility_id, ln.boe_id, r.role FROM legal_fragment_responsibilities r JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id JOIN sanction_norm_catalog c ON c.norm_id = l.norm_id JOIN legal_norms ln ON ln.norm_id = c.norm_id), flags AS (SELECT b.*, EXISTS(SELECT 1 FROM legal_fragment_responsibility_evidence e WHERE e.responsibility_id=b.responsibility_id AND e.evidence_type IN ('congreso_diario','senado_diario','congreso_vote','senado_vote')) AS has_parliamentary_any, EXISTS(SELECT 1 FROM legal_fragment_responsibility_evidence e WHERE e.responsibility_id=b.responsibility_id AND e.evidence_type IN ('congreso_vote','senado_vote')) AS has_vote FROM base b) SELECT * FROM flags WHERE has_parliamentary_any=0 OR has_vote=0 ORDER BY boe_id, role;" > docs/etl/sprints/AI-OPS-171/evidence/responsibility_parliamentary_vote_gap_20260224T094041Z.csv`
  - `sqlite3 etl/data/staging/politicos-es.db 'PRAGMA foreign_key_check;'`
- Tests:
  - `just parl-test-sanction-norms-seed`
  - `just parl-test-liberty-restrictions`

## Result
Coverage deltas vs AI-OPS-170:
- `responsibility_evidence_items_total`: `97 -> 99` (`+2`)
- `responsibility_evidence_items_parliamentary_total`: `46 -> 48` (`+2`)
- `responsibility_evidence_items_parliamentary_vote_total`: stays `44`
- `responsibilities_with_parliamentary_evidence_total`: `13/15 -> 15/15` (`0.866667 -> 1.0`)
- `responsibilities_with_parliamentary_vote_evidence_total`: stays `13/15`
- `responsibilities_with_execution_evidence_total`: stays `15/15`
- `queue_rows_total`: stays `0`
- `fk_violations_total`: stays `0`

Backfill stats (AI-OPS-171):
- Parliamentary backfill:
  - `candidate_matches_total=3`
  - `evidence_inserted=2`
  - `evidence_updated=2`
  - `docs_with_title_rule_match_total=1`
  - `by_method`: `text_excerpt_boe_id_regex=2`, `title_rule:lisos_orden_social=1`
- Vote backfill:
  - `candidate_matches_total=71`
  - `evidence_inserted=0`
  - `evidence_updated=123`

## Remaining gap
Vote-only gap remains on:
- `BOE-A-2000-15060` (`approve`, `enforce`)

Current state from gap snapshot:
- `has_parliamentary_any=1`, `has_vote=0` for both roles.
- Quick probe on vote-linked initiative titles returns no exact LISOS phrase match (`vote_initiatives_with_lisos_phrase=0`), so there is no conservative same-pattern vote bridge yet.

## Evidence
- `docs/etl/sprints/AI-OPS-171/evidence/sanction_norms_parliamentary_evidence_backfill_20260224T094041Z.json`
- `docs/etl/sprints/AI-OPS-171/evidence/sanction_norms_vote_evidence_backfill_20260224T094041Z.json`
- `docs/etl/sprints/AI-OPS-171/evidence/sanction_norms_seed_status_20260224T094041Z.json`
- `docs/etl/sprints/AI-OPS-171/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T094041Z.json`
- `docs/etl/sprints/AI-OPS-171/evidence/responsibility_parliamentary_vote_gap_20260224T094041Z.csv`
- `docs/etl/sprints/AI-OPS-171/evidence/sqlite_fk_check_20260224T094041Z.txt`
- `docs/etl/sprints/AI-OPS-171/evidence/just_parl_test_sanction_norms_seed_20260224T094041Z.txt`
- `docs/etl/sprints/AI-OPS-171/evidence/just_parl_test_liberty_restrictions_20260224T094041Z.txt`
