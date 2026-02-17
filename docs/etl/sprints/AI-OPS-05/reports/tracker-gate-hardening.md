# AI-OPS-05 Tracker Gate Hardening

Date: 2026-02-16  
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Objective

Promote tracker mismatch detection to default operational gate while keeping backward-compatible command docs.

## Changes applied

1. `justfile`
- `etl-tracker-gate` is now strict by default:
  - `--fail-on-mismatch`
  - `--fail-on-done-zero-real`
- Added compatibility target:
  - `etl-tracker-gate-legacy` (historical behavior: only `--fail-on-done-zero-real`)

2. Docs command compatibility
- Updated `docs/etl/e2e-scrape-load-tracker.md` shortcuts to document:
  - strict default gate (`just etl-tracker-gate`)
  - legacy compatibility gate (`just etl-tracker-gate-legacy`)
- Updated `docs/etl/sprints/AI-OPS-05/evidence/tracker-reconciliation.md` commands section with strict+legacy semantics.

3. Focused test adjustment
- Extended `tests/test_e2e_tracker_status_tracker.py` with CLI regression check:
  - `--fail-on-mismatch` returns non-zero on mismatch.

## Command evidence

### A) Gate definition in `justfile`

Command:
```bash
rg -n "etl-tracker-gate|fail-on-mismatch" justfile
```

Output:
```text
540:etl-tracker-gate:
541:  docker compose run --rm --build etl "python3 scripts/e2e_tracker_status.py --db {{db_path}} --tracker {{tracker_path}} --fail-on-mismatch --fail-on-done-zero-real"
544:etl-tracker-gate-legacy:
```

### B) Tracker tests

Command:
```bash
python3 -m unittest discover -s tests -p 'test*tracker*py'
```

Output:
```text
Ran 5 tests in 0.004s
OK
```

### C) Strict default gate behavior (`just etl-tracker-gate`)

Command:
```bash
just etl-tracker-gate
```

Observed result:
```text
FAIL: checklist/sql mismatches detected.
...
mismatches: 3
done_zero_real: 0
error: Recipe `etl-tracker-gate` failed ... exit code 1
```

Mismatch rows in this run:
- `moncloa_referencias` (`checklist=PARTIAL`, `sql=DONE`)
- `moncloa_rss_referencias` (`checklist=PARTIAL`, `sql=DONE`)
- `parlamento_navarra_parlamentarios_forales` (`checklist=PARTIAL`, `sql=DONE`)

Interpretation:
- Gate now fails fast on reconciliation drift, as intended.

## Escalation rule handling

Condition met:
- Strict gate fails due unresolved mismatch/blocked volatility.

Proposed scoped allowlist (not applied; requires L3 approval before merge):
- Temporary mismatch allowlist by `source_id`:
  - `parlamento_navarra_parlamentarios_forales` (blocked WAF/Cloudflare behavior)
  - `moncloa_referencias`
  - `moncloa_rss_referencias`
- Scope guard:
  - apply only to `--fail-on-mismatch` path,
  - enforce expiry by snapshot date,
  - keep `--fail-on-done-zero-real` always active.

Current decision:
- No allowlist implemented in code in this task.
- Keep strict gate active by default and treat current non-zero exit as expected until tracker reconciliation closes these mismatches.

