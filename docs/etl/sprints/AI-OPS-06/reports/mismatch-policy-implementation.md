# AI-OPS-06 Mismatch Policy Implementation

Date: 2026-02-16  
Repository: `REPO_ROOT/vota-con-la-chola`

## Objective

Implement explicit mismatch-policy contract in tracker checker so strict gating is deterministic and auditable:
- fail on unwaived mismatches,
- fail on expired waivers,
- keep `DONE_ZERO_REAL` as hard-fail.

## What changed

### 1) Checker contract (`scripts/e2e_tracker_status.py`)

Added waiver input support:
- `--waivers <path>` (default: `docs/etl/mismatch-waivers.json`)
- `--as-of-date YYYY-MM-DD` for deterministic expiry evaluation

Waiver schema (required per item):
- `source_id`
- `reason`
- `owner`
- `expires_on`

Validation rules:
- invalid/missing required fields -> error exit
- duplicate `source_id` in waiver file -> error exit
- expired waiver (`as_of_date > expires_on`) is not active

Output behavior:
- mismatch + active waiver -> `WAIVED_MISMATCH`
- mismatch without active waiver (including expired waiver) -> `MISMATCH`
- `DONE` with zero network load -> `DONE_ZERO_REAL` (unchanged hard rule)

New report counters:
- `mismatches`
- `waived_mismatches`
- `waivers_active`
- `waivers_expired`
- `done_zero_real`

### 2) Waiver registry seed

Added empty default waiver registry:
- `docs/etl/mismatch-waivers.json`

Demo evidence files used in this sprint:
- `docs/etl/sprints/AI-OPS-06/evidence/mismatch-waivers-demo.json`
- `docs/etl/sprints/AI-OPS-06/evidence/mismatch-waivers-all-active-demo.json`

### 3) Focused tests

Updated:
- `tests/test_e2e_tracker_status_tracker.py`

Added coverage for:
- waiver parsing (active vs expired by `expires_on`)
- `--fail-on-mismatch` pass with active waiver
- `--fail-on-mismatch` fail with expired waiver
- `DONE_ZERO_REAL` still failing even when mismatch is waived

## Before/After gate behavior

### A) Baseline strict mismatch gate (no waivers)

Command:
```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --fail-on-mismatch
```

Observed summary:
```text
mismatches: 3
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
EXIT_CODE:1
```

### B) Mixed waiver set (2 active + 1 expired)

Command:
```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/sprints/AI-OPS-06/evidence/mismatch-waivers-demo.json \
  --as-of-date 2026-02-16 \
  --fail-on-mismatch
```

Observed summary:
```text
mismatches: 1
waived_mismatches: 2
waivers_active: 2
waivers_expired: 1
done_zero_real: 0
EXIT_CODE:1
```

Row-level evidence includes both:
- `WAIVED_MISMATCH` (Moncloa rows)
- `MISMATCH` (Navarra, because waiver is expired)

### C) All mismatches actively waived

Command:
```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/sprints/AI-OPS-06/evidence/mismatch-waivers-all-active-demo.json \
  --as-of-date 2026-02-16 \
  --fail-on-mismatch
```

Observed summary:
```text
mismatches: 0
waived_mismatches: 3
waivers_active: 3
waivers_expired: 0
done_zero_real: 0
EXIT_CODE:0
```

### D) `DONE_ZERO_REAL` enforcement unchanged

Command:
```bash
python3 -m unittest tests.test_e2e_tracker_status_tracker.TestE2ETrackerStatusTrackerRules.test_done_zero_real_enforcement_not_weakened_by_waiver
```

Observed output:
```text
FAIL: DONE sources with zero real-network loaded records detected.
...
result = DONE_ZERO_REAL
done_zero_real: 1
Ran 1 test ... OK
```

Interpretation:
- Waivers do not bypass `DONE_ZERO_REAL`.

## Acceptance evidence commands

```bash
python3 -m unittest discover -s tests -p 'test*tracker*py'
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md
rg -n "WAIVED_MISMATCH|expires_on|fail-on-mismatch" docs/etl/sprints/AI-OPS-06/reports/mismatch-policy-implementation.md
```

