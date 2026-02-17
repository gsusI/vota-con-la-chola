# AI-OPS-08 Tracker Gate Policy Default Hardening

Date: 2026-02-16
Repository: `REPO_ROOT/vota-con-la-chola`

## Objective

Harden default tracker gate ergonomics with a canonical waiver registry path while preserving strict fail semantics.

## Implemented changes

1) Canonical waiver registry standardized
- File: `docs/etl/mismatch-waivers.json`
- Action: seeded canonical operational waiver registry with current approved waiver:
  - `parlamento_navarra_parlamentarios_forales` (expires `2026-02-20`).

2) Default tracker gate wired to canonical waiver path
- File: `justfile`
- Added variable:
  - `tracker_waivers_path := env_var_or_default("TRACKER_WAIVERS_PATH", "docs/etl/mismatch-waivers.json")`
- Updated targets:
  - `etl-tracker-status` now passes `--waivers {{tracker_waivers_path}}`
  - `etl-tracker-gate` now passes `--waivers {{tracker_waivers_path}} --fail-on-mismatch --fail-on-done-zero-real`
- Kept backward-compatible target:
  - `etl-tracker-gate-legacy` remains available.

3) Docs made explicit on strict vs legacy behavior
- File: `docs/etl/e2e-scrape-load-tracker.md`
- Updated shortcut text to state:
  - strict default uses `docs/etl/mismatch-waivers.json` and fails on unwaived mismatch / expired waiver / `DONE_ZERO_REAL`.
  - legacy keeps historical compatibility (only `DONE_ZERO_REAL` enforcement).
- Updated row command references to canonical waiver path.

4) Focused test adjustment
- File: `tests/test_e2e_tracker_status_tracker.py`
- Added test:
  - `test_default_waivers_path_is_canonical_registry`

## Before / after snapshot

### Before hardening (default gate did not consume active waiver registry)
Command:
```bash
just etl-tracker-gate || true
```
Key output (from `/tmp/aiops08_gate_before_default.log`):
```text
boe_api_legal                             | PARTIAL | DONE | ... | MISMATCH
parlamento_navarra_parlamentarios_forales | PARTIAL | DONE | ... | MISMATCH
mismatches: 2
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
```

### After hardening (default gate consumes canonical waiver registry)
Command:
```bash
just etl-tracker-gate || true
```
Key output (from `/tmp/aiops08_gate_after_default_full.log`):
```text
boe_api_legal                             | PARTIAL | DONE | ... | MISMATCH
parlamento_navarra_parlamentarios_forales | PARTIAL | DONE | ... | WAIVED_MISMATCH
mismatches: 1
waived_mismatches: 1
waivers_active: 1
waivers_expired: 0
done_zero_real: 0
FAIL: checklist/sql mismatches detected.
```

Exit behavior:
```text
strict_exit=1
legacy_exit=0
```

Interpretation:
- Strict default still fails when an unwaived mismatch exists (`boe_api_legal`), so no masking regression.
- Approved active waiver is now applied deterministically (`parlamento_navarra_parlamentarios_forales` -> `WAIVED_MISMATCH`).
- Expired waivers and `DONE_ZERO_REAL` remain in strict fail path by contract.

## Moncloa non-regression check

Command:
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json
```

Relevant output:
```text
moncloa_referencias     | DONE | DONE | ... | OK
moncloa_rss_referencias | DONE | DONE | ... | OK
```

No Moncloa regression introduced by this change.

## Commands run for validation

```bash
python3 -m unittest discover -s tests -p 'test*tracker*py'
rg -n "etl-tracker-gate|etl-tracker-gate-legacy|mismatch-waivers.json|fail-on-mismatch" justfile
just etl-tracker-gate || true
just etl-tracker-gate-legacy || true
```
