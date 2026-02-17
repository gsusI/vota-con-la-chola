# AI-OPS-06 mismatch policy apply & recompute report

## Inputs
- `docs/etl/sprints/AI-OPS-06/exports/mismatch_candidates.csv`
- `docs/etl/sprints/AI-OPS-06/exports/waiver_candidates.csv`
- Policy materialization target: `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json`
- DB/Tracker: `etl/data/staging/politicos-es.db`, `docs/etl/e2e-scrape-load-tracker.md`

## Applied policy artifact
Created: `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json`
- `waivers_active`: 3
- `approver`: `L3`
- `as_of_date`: `2026-02-16`

## Checker matrix executed

### 1) Baseline checker (no policy)
**Command**
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md
```
**Log**: `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-baseline-check.log`
**Exact summary output**
```text
FAIL: checklist/sql mismatches detected.
tracker_sources: 30
sources_in_db: 32
mismatches: 3
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
EXIT_CODE:0
```

### 2) Strict gate (`just etl-tracker-gate`)
**Command**
```bash
just etl-tracker-gate
```
**Log**: `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log`
**Exact summary output**
```text
tracker_sources: 30
sources_in_db: 32
mismatches: 3
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0

error: Recipe `etl-tracker-gate` failed on line 541 with exit code 1
EXIT_CODE:1
```

### 3) Explicit mismatch-fail path with applied waivers
**Command**
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real
```
**Log**: `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-explicit-mismatch-fail.log`
**Exact summary output**
```text
tracker_sources: 30
sources_in_db: 32
mismatches: 0
waived_mismatches: 3
waivers_active: 3
waivers_expired: 0
done_zero_real: 0
EXIT_CODE:0
```
This run marks source rows for:
- `moncloa_referencias` -> `WAIVED_MISMATCH`
- `moncloa_rss_referencias` -> `WAIVED_MISMATCH`
- `parlamento_navarra_parlamentarios_forales` -> `WAIVED_MISMATCH`

### 4) Legacy gate (`just etl-tracker-gate-legacy`)
**Command**
```bash
just etl-tracker-gate-legacy
```
**Log**: `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-legacy-gate.log`
**Exact summary output**
```text
tracker_sources: 30
sources_in_db: 32
mismatches: 3
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
EXIT_CODE:0
```

## Before/after mismatch / done_zero_real
- **Before explicit waivers**: `mismatches: 3`, `done_zero_real: 0`
- **After explicit mismatch policy**: `mismatches: 0` (all three were `WAIVED_MISMATCH`), `done_zero_real: 0`

## Escalation condition outcome
Strict gate still fails on unwaived mismatches (as expected). Exact failing source IDs:
- `moncloa_referencias`
- `moncloa_rss_referencias`
- `parlamento_navarra_parlamentarios_forales`

Supporting evidence:
- `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log`
- `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-baseline-check.log`
- `docs/etl/sprints/AI-OPS-06/exports/mismatch_candidates.csv`
