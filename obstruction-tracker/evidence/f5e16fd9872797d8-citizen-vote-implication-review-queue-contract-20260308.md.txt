# AI-OPS-553: Citizen Vote Implication Review Queue Contract

Date: `2026-03-08`

## Where We Are Now

- The vote ingestion/publish stack can already link `vote_event_id -> initiative_id -> docs`.
- The citizen-facing weakness is semantic: many parliamentary titles are procedural wrappers and do not explain the practical stake of the vote.
- This blocks compelling micro-insights and citizen comprehension even when the raw evidence exists.

## Where We Are Going

- Add a controllable, reviewable lane for translating official vote events into citizen-facing implications.
- Keep it additive and auditable:
  - SQLite queue table
  - export CSV for agent/manual review
  - apply reviewed decisions back into SQLite
  - no auto-publish of inferred meaning without review

## What Shipped In This Slice

- Additive schema table: `parl_vote_implication_reviews`
- Queue export script: `scripts/export_vote_implication_review_queue.py`
- Review apply script: `scripts/apply_vote_implication_reviews.py`
- Operator/reviewer contract: `docs/etl/citizen-vote-implication-review-instructions.md`
- Focused tests for export/apply queue behavior

## Verification

- `python3 -m unittest tests.test_export_vote_implication_review_queue tests.test_apply_vote_implication_reviews`
- `python3 -m py_compile scripts/export_vote_implication_review_queue.py scripts/apply_vote_implication_reviews.py`
- Real queue export on `etl/data/staging/politicos-es.db`:
  - `candidate_rows=2823`
  - `priority=100` rows: `716`
  - narrow-margin rows (`|yes-no| <= 5`): `174`
  - dominant reasons: `generic_title=1750`, `split_vote_point=585`, `missing_excerpt=483`
  - cleanup gate: `file_url_rows_remaining=0`
- Evidence:
  - `docs/etl/sprints/AI-OPS-553/evidence/vote_implication_review_queue_sample_20260308T174909Z.csv`
  - `docs/etl/sprints/AI-OPS-553/evidence/vote_implication_review_queue_export_20260308T174909Z.txt`
  - `docs/etl/sprints/AI-OPS-553/evidence/vote_implication_review_queue_stats_20260308T175054Z.txt`
  - `docs/etl/sprints/AI-OPS-553/evidence/vote_implication_review_queue_daily_life_seed_20260308T175204Z.csv`
  - `docs/etl/sprints/AI-OPS-553/evidence/vote_implication_review_queue_daily_life_seed_20260308T175204Z.txt`

## First Agent/Reviewer Seed Batch

- Added export filters so batches can be cut by:
  - `review_reason`
  - yes/no margin
  - text contains across official title/subject/subgroup
- First targeted batch exported:
  - scope: `split_vote_point + margin <= 5 + vida cotidiana`
  - terms: `vivienda`, `movilidad`, `cliente`, `transporte`, `energ`, `presupuestaria`
  - rows: `8`
- The first seed already surfaces the kind of cases this lane is meant to fix:
  - housing motions split by points
  - mobility bill amendments with razor-thin margins
  - customer-service bill amendment votes
  - transport-sector precariousness motion

## Delegation Package Ready

- Added a ready-to-run delegation package for the first 8-row seed batch:
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/DelegationPackage.json`
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/DelegationPackage.md`
- Added execution artifacts for immediate rollout:
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/ExecutionQueue.json`
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/AggregationGuide.md`
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/cards/WS1-*.md`
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/results/README.md`
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/results/raw-submissions/.gitkeep`
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/results/adjudicated/.gitkeep`
- Scope of the ready batch:
  - `8` independent microtasks
  - `double` redundancy on every task
  - one hidden golden sample (`WS1-008-B`)
  - 100% adjudication for the pilot

## Local Fallback Integrated

- The first live microtask execution confirmed `HTTP 403 Access Denied` on Congreso `VOT_*.json` event URLs from this environment.
- To keep the pilot executable, the delegation bundle now includes:
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/local-evidence/WS1-*.json`
  - updated worker cards instructing agents/reviewers to use the local fallback when official URLs fail
- Each local-evidence artifact includes:
  - the original seed row
  - the matching `parl_vote_events` row
  - parsed `raw_payload_info` (including `textoSubGrupo` / point label)
  - any local doc extraction or text-document payload already present
  - references to the 403 evidence files when network access is blocked
- Pilot raw submissions now include honest blocked outputs under:
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/results/raw-submissions/WS1-006-A.json`
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/results/raw-submissions/WS1-008-A.json`

## Pilot Execution Signal

- First real microtask execution against `WS1-008` hit upstream blockage on the official vote-event URL:
  - `HTTP 403`
  - `content-type=text/html`
  - body `Access Denied`
- This does not invalidate the lane; it clarifies the operational constraint:
  - worker cards and batch routing are ready
  - execution from this environment needs fallback to already-ingested raw/doc evidence or an alternate official endpoint for per-vote URLs
- Evidence:
  - `docs/etl/sprints/AI-OPS-553/evidence/congreso_vote_event_url_403_headers_20260308T180003Z.txt`
  - `docs/etl/sprints/AI-OPS-553/evidence/congreso_vote_event_url_403_body_20260308T180003Z.html`
  - `docs/etl/sprints/AI-OPS-553/delegation/daily-life-seed-20260308/results/WS1-008.blocked.20260308T180035Z.json`

## Design Decisions

- Unit of review: one `review_key`, typically `vote_event_id + initiative_id`
- Primary reasons for review:
  - `split_vote_point`
  - `generic_title`
  - `procedural_wrapper`
  - `subject_low_specificity`
  - `missing_excerpt`
- The queue stores both heuristic hints and final reviewed citizen text.
- Reviewed output is intentionally constrained:
  - `citizen_title`
  - `citizen_question`
  - `citizen_summary`
  - `impact_if_approved`
  - `impact_if_rejected`
  - `affected_groups`
  - `evidence_quote`

## Next

1. Start review batches with the intersection `split_vote_point + narrow margin + everyday-life themes`.
2. Prioritize concrete cases already surfacing in the queue: `vivienda`, `movilidad sostenible`, `servicios de atención al cliente`, `presupuestaria`.
3. Reuse resolved implication text later in `/citizen` and political-positions explainability surfaces.
