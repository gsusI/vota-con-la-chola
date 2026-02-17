# Sprint AI-OPS-07 Kickoff

Date: 2026-02-16  
Repository: `REPO_ROOT/vota-con-la-chola`

## Sprint Focus

Moncloa-BOE dual-entry validation plus waiver burn-down, preserving strict mismatch-policy auditability.

## Objective

Freeze PASS/FAIL conditions and execution order so L2/L1 can run deterministically with no gate ambiguity.

## Inputs Reviewed

- `docs/roadmap.md`
- `docs/roadmap-tecnico.md`
- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-06/closeout.md`
- `docs/gh-pages/explorer-sources/data/status.json`
- `sqlite3 etl/data/staging/politicos-es.db`

## Baseline Commands (Exact Outputs)

### 1) Tracker status baseline

Command:
```bash
just etl-tracker-status
```

Exact gate-relevant output lines:
```text
moncloa_referencias                       | PARTIAL   | DONE    | 7/8           | 2       | 20      | 20          | 2/5                  | MISMATCH
moncloa_rss_referencias                   | PARTIAL   | DONE    | 8/10          | 8       | 8       | 8           | 2/6                  | MISMATCH
parlamento_navarra_parlamentarios_forales | PARTIAL   | DONE    | 3/8           | 50      | 50      | 50          | 1/2                  | MISMATCH
tracker_sources: 30
sources_in_db: 32
mismatches: 3
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
```

### 2) Strict tracker gate (non-blocking probe)

Command:
```bash
just etl-tracker-gate || true
```

Exact gate-relevant output lines:
```text
FAIL: checklist/sql mismatches detected.
mismatches: 3
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
error: Recipe `etl-tracker-gate` failed on line 541 with exit code 1
```

### 3) Policy-aware explicit mismatch check

Command:
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real
```

Exact gate-relevant output lines:
```text
moncloa_referencias                       | PARTIAL   | DONE    | 7/8           | 2       | 20      | 20          | 2/5                  | WAIVED_MISMATCH
moncloa_rss_referencias                   | PARTIAL   | DONE    | 8/10          | 8       | 8       | 8           | 2/6                  | WAIVED_MISMATCH
parlamento_navarra_parlamentarios_forales | PARTIAL   | DONE    | 3/8           | 50      | 50      | 50          | 1/2                  | WAIVED_MISMATCH
tracker_sources: 30
sources_in_db: 32
mismatches: 0
waived_mismatches: 3
waivers_active: 3
waivers_expired: 0
done_zero_real: 0
```

### 4) FK integrity

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Output:
```text
fk_violations
-------------
0
```

### 5) Review queue health

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"
```

Output:
```text
topic_evidence_reviews_pending
------------------------------
0
```

### 6) Moncloa action baseline

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_moncloa FROM policy_events WHERE source_id LIKE 'moncloa_%';"
```

Output:
```text
policy_events_moncloa
---------------------
28
```

### 7) BOE source presence baseline

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, name, is_active FROM sources WHERE lower(source_id) LIKE '%boe%' OR lower(name) LIKE '%boe%' OR lower(name) LIKE '%bolet%';"
```

Output:
```text
(no rows)
```

## Baseline Snapshot (Locked)

- `fk_violations = 0`
- `topic_evidence_reviews_pending = 0`
- `policy_events_moncloa = 28`
- BOE rows in `sources` (LIKE `boe`/`bolet`) = `0`
- Raw strict mismatch state: `mismatches = 3`, `done_zero_real = 0`
- Policy-aware state (`as_of_date=2026-02-16`, approved waivers): `mismatches = 0`, `waived_mismatches = 3`, `waivers_active = 3`, `waivers_expired = 0`

## Must-Pass Gates (AI-OPS-07)

| Gate | PASS condition | Evidence command |
|---|---|---|
| Gate G1 Data integrity | `fk_violations = 0` | `sqlite3 ... "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"` |
| Gate G2 Queue health | `topic_evidence_reviews_pending = 0` | `sqlite3 ... "SELECT COUNT(*) AS topic_evidence_reviews_pending ..."` |
| Gate G3 Strict behavior clarity | strict unwaived path remains failing when mismatches exist; explicit waiver-aware fail path is deterministic (`done_zero_real=0`) | `just etl-tracker-gate || true` + waiver-aware checker command |
| Gate G4 BOE onboarding | BOE source(s) exist in `sources` and at least one BOE ingest run has `records_loaded > 0` | `sqlite3 ... sources LIKE boe` + `sqlite3 ... ingestion_runs WHERE source_id LIKE 'boe_%'` |
| Gate G5 Dual-entry action traceability | `policy_events_boe > 0`, and BOE/Moncloa `policy_events` rows keep `source_id`, `source_url`, `source_record_pk` traceability | SQL counts + mapping report |
| Gate G6 Waiver burn-down governance | unwaived mismatches remain `0`; no expired waivers; Moncloa waivers reduced to `0` by closeout | waiver-aware checker output + waiver artifact + tracker reconciliation evidence |
| Gate G7 Workload balance | L1 delivered majority throughput evidence (>=50% task share and artifact completion) | sprint prompt pack + artifact existence checks |

## Ordered Execution Sequence (Locked)

1. `T1` Kickoff + baseline freeze (this doc).
2. `T2` Implement BOE connector (L2).
3. `T3` Map BOE to `policy_events` (L2).
4. `T4` Build Moncloa-BOE reconciliation/waiver burn-down candidate exports (L1).
5. `T5` Apply/recompute and capture gate deltas (L1).
6. `T6` Reconcile tracker rows with fresh evidence (L1).
7. `T7` Publish final evidence packet + dashboard parity (L1).
8. `T8` Closeout PASS/FAIL (L3).

Dependency order (critical path):
- `T1 -> (T2,T3) -> T5 -> T6 -> T7 -> T8`
- `T4` runs after `(T2,T3)` and feeds reconciliation decisions.

## PASS/FAIL Policy Lock

- **PASS** only if `Gate G1-G7` are all green in the same sprint evidence set.
- **FAIL** if any gate is red; carryover must include owner, blocker evidence, and first command.
- Waivers are temporary controls, not completion criteria; waiver expiry must not cross sprint closeout without explicit L3 decision.
