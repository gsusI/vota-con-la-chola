# Sprint AI-OPS-06 Kickoff

Date: 2026-02-16  
Repository: `REPO_ROOT/vota-con-la-chola`  
Sprint focus: mismatch-policy governance and strict gate recovery

## Objective (frozen)

Lock PASS/FAIL gates and the mismatch decision policy before implementation so L2/L1 tasks run deterministically.

## Inputs read

- `docs/roadmap.md`
- `docs/roadmap-tecnico.md`
- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-05/closeout.md`
- `docs/etl/sprints/AI-OPS-05/reports/tracker-gate-hardening.md`
- `docs/gh-pages/explorer-sources/data/status.json`

Roadmap alignment used:
- `docs/roadmap.md` section 4.3: keep first non-parliament action source (Moncloa) on critical path with traceable evidence.
- `docs/roadmap-tecnico.md` quality contract: reproducible tracking + explicit gates.
- `docs/etl/sprints/AI-OPS-05/closeout.md`: carryover requires resolving strict tracker gate drift (`mismatches=3`).

## Baseline Commands and Exact Outputs

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
done_zero_real: 0
```

### 2) Strict gate baseline (non-blocking probe)

Command:
```bash
just etl-tracker-gate || true
```

Exact gate-relevant output lines:
```text
FAIL: checklist/sql mismatches detected.
mismatches: 3
done_zero_real: 0
error: Recipe `etl-tracker-gate` failed on line 541 with exit code 1
```

### 3) Data integrity baseline

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Output:
```text
0
```

## Baseline snapshot (frozen)

- `fk_violations = 0`
- `mismatches = 3`
- `done_zero_real = 0`
- mismatch source_ids:
  - `moncloa_referencias`
  - `moncloa_rss_referencias`
  - `parlamento_navarra_parlamentarios_forales`
- explorer-sources still shows Moncloa rows present:
  - `moncloa_referencias` (`tracker_status=PARTIAL`, `sql_status=DONE`)
  - `moncloa_rss_referencias` (`tracker_status=PARTIAL`, `sql_status=DONE`)

## decision rubric (mismatch handling)

| Policy path | Use when | Required evidence | Owner |
|---|---|---|---|
| `RECONCILE_TRACKER_ROW` | Mismatch is due to stale tracker wording/status and operational truth is stable enough to update row semantics. | `just etl-tracker-status` row + tracker line update diff + one reproducible next command in tracker row. | L2 |
| `TEMP_WAIVER` | Mismatch remains intentional for a bounded period (e.g., blocked/volatility semantics) and changing tracker row now would misrepresent blocker reality. | source-level blocker proof (command + output), explicit rationale, and strict gate impact (`mismatches` row list). | L3 approval, L2 execution |

Waiver requirements (mandatory):
1. `source_id` list is explicit (no wildcards).
2. `owner` is explicit (`L2` default), plus `approved_by` (`L3`).
3. `expires_on` required in `YYYY-MM-DD`; max horizon: next sprint closeout.
4. `reason` + `blocker_evidence_path` + `first remediation command` are required.
5. Expired waiver is treated as unwaived mismatch and fails gate.
6. Waiver never bypasses `done_zero_real`; that check remains hard-fail.

## Ordered gates (AI-OPS-06)

| Gate | PASS condition | Evidence command |
|---|---|---|
| Gate G1 Integrity | `fk_violations = 0` | `sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"` |
| Gate G2 Real-load safety | `done_zero_real = 0` | `just etl-tracker-status` |
| Gate G3 Mismatch disposition completeness | Every mismatch is classified as `RECONCILE_TRACKER_ROW` or `TEMP_WAIVER` with recorded owner. | mismatch policy artifact + `just etl-tracker-status` |
| Gate G4 Waiver governance | Any temporary waiver has `source_id`, `owner`, `approved_by`, `expires_on`, `reason`, `blocker_evidence_path`, `first remediation command`. | waiver registry diff + report |
| Gate G5 Effective mismatch closure | `effective_mismatches = 0` (raw mismatches minus active, non-expired, approved waivers). | strict checker/report command set |
| Gate G6 Strict gate decision | `just etl-tracker-gate` passes, or explicit waiver-aware strict variant passes with approved waivers and no expired waivers. | gate command output |

## Execution order (frozen)

1. T1 Freeze baseline and rubric (this kickoff).
2. T2 Implement mismatch-policy contract in checker (classification + expiry behavior).
3. T3 Expose mismatch-policy visibility in explorer-sources payload.
4. T4 Prepare/validate waiver packet only if still needed after reconciliation attempts.
5. T5 Re-run strict gate path and compute effective mismatches.
6. T6 Closeout PASS/FAIL.

## PASS/FAIL lock

- **PASS** only if G1-G6 are all green in the same evidence run.
- **FAIL** if any gate fails; carryover must include owner, blocker evidence, and first command.
