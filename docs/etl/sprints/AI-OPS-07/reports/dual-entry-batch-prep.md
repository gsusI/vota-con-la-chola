# AI-OPS-07 dual-entry batch-prep report

## Scope
- Deterministic Moncloa-BOE reconciliation candidates
- Waiver burn-down candidates for active mismatch waivers

## Commands executed
1. Tracker status snapshot for current statuses
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md | tee docs/etl/sprints/AI-OPS-07/evidence/tracker-status-ai-ops-07.log
```

2. Candidate export + waiver derivation script (policy_events pull, deterministic matching, CSV writes)
```bash
python3 - <<'PY' | tee docs/etl/sprints/AI-OPS-07/evidence/dual-entry-generation.log
# 1) export policy_events for moncloa_/boe_
# 2) deterministic token/date matching with threshold (0.30)
# 3) build moncloa_boe_reconciliation_candidates.csv
# 4) load active waivers and build waiver_burndown_candidates.csv
PY
```

## Evidence artifacts
- Tracker status output: `docs/etl/sprints/AI-OPS-07/evidence/tracker-status-ai-ops-07.log`
- Candidate generation log: `docs/etl/sprints/AI-OPS-07/evidence/dual-entry-generation.log`
- SQL evidence extract: `docs/etl/sprints/AI-OPS-07/evidence/moncloa_boe_policy_events_raw.csv`

## Outputs produced
- `docs/etl/sprints/AI-OPS-07/exports/moncloa_boe_reconciliation_candidates.csv`
- `docs/etl/sprints/AI-OPS-07/exports/waiver_burndown_candidates.csv`

## Matching method (deterministic)
- Candidate source set: `policy_events` rows where `source_id LIKE 'moncloa_%'` and `event_date >= 2026-01-01`.
- BOE candidate set: all `source_id LIKE 'boe_%'` from `policy_events`.
- Date normalization from `event_date` and BOE-derived date from title/source URL.
- Token similarity over `(title + summary)` with stopword-stripped, lowercased tokens.
- Match chosen per Moncloa event as highest-confidence BOE candidate.
- `match_rule = UNRESOLVED` when no deterministic rule/threshold (`match_confidence < 0.30`) is met.

## Final counts
- Moncloa-BOE rows considered: `10`
- Candidates with deterministic BOE match: `0`
- Candidates flagged `UNRESOLVED`: `10`

## Escalation result
- No deterministic Moncloa-BOE evidence links were found with current policy_events extract.
- Reproducible result: all candidate rows remain `UNRESOLVED` and should stay out of the apply set.

## File-specific status

### `moncloa_boe_reconciliation_candidates.csv`
- Includes required columns: `moncloa_event_id`, `boe_event_id`, `match_rule`, `match_confidence`.
- `UNRESOLVED` rows are explicit and retain full traceability (event IDs + titles).

### `waiver_burndown_candidates.csv`
- Includes required columns: `waiver_expires_on`, `recommendation`.
- `recommendation` is set to `UNRESOLVED` for all active waivers where deterministic dual-entry proof is missing.

## Reproducibility notes
- Re-run same commands in the same DB snapshot (`etl/data/staging/politicos-es.db`) to reproduce identical CSVs.
- Evidence links used in recommendations and blockers remain stable and are file-referenced for audit.
