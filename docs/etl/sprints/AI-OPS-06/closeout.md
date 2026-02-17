# Sprint AI-OPS-06 Closeout

Date: 2026-02-16  
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Decision

**PASS**

Reason: G1-G6 are green under the approved mismatch-policy contract (explicit waiver mode as of `2026-02-16`) and strict fail behavior remains auditable for unwaived mismatches.

## Gate Results

| Gate | Check | Result | Status |
|---|---|---|---|
| G1 | `fk_violations=0` | `fk_violations=0` | PASS |
| G2 | `topic_evidence_reviews_pending=0` | `topic_evidence_reviews_pending=0` | PASS |
| G3 | strict gate result documented and policy-consistent | strict unwaived path fails (`EXIT_CODE:1`, expected); explicit waiver path passes (`EXIT_CODE:0`) | PASS |
| G4 | unwaived mismatches = 0 | policy-aware checker run: `mismatches=0`, `waived_mismatches=3`, `waivers_active=3` | PASS |
| G5 | tracker row wording reconciled with evidence | Moncloa/Navarra/Galicia rows include blocker context + deterministic next command, aligned with reconciliation evidence | PASS |
| G6 | L1 majority throughput evidence present | `L1 = 16 pts (59.3%)`, `L1 task share = 4/8 (50%)`, L1 artifact set present | PASS |

## Evidence Commands and Outputs

### G1

Command:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Output:
```text
fk_violations
-------------
0
```

### G2

Command:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"
```

Output:
```text
topic_evidence_reviews_pending
------------------------------
0
```

### G3

Command:
```bash
rg -n "mismatches:|waived_mismatches:|waivers_active:|done_zero_real:|EXIT_CODE:|FAIL:" docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-explicit-mismatch-fail.log
```

Output:
```text
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log:58:FAIL: checklist/sql mismatches detected.
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log:96:mismatches: 3
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log:97:waived_mismatches: 0
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log:98:waivers_active: 0
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log:100:done_zero_real: 0
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log:103:EXIT_CODE:1
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-explicit-mismatch-fail.log:38:mismatches: 0
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-explicit-mismatch-fail.log:39:waived_mismatches: 3
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-explicit-mismatch-fail.log:40:waivers_active: 3
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-explicit-mismatch-fail.log:42:done_zero_real: 0
docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-explicit-mismatch-fail.log:43:EXIT_CODE:0
```

### G4

Command:
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real | tail -n 8; echo EXIT_CODE:$?
```

Output:
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

### G5

Command:
```bash
rg -n "Accion ejecutiva \(Consejo de Ministros\)|Parlamento de Navarra|Parlamento de Galicia" docs/etl/e2e-scrape-load-tracker.md
rg -n "Siguiente comando|Current blocker|Done now" docs/etl/sprints/AI-OPS-06/evidence/tracker-row-reconciliation.md
```

Output:
```text
45:| Representantes y mandatos (Parlamento de Galicia) | ... | PARTIAL | ... Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --strict-network --timeout 30`. |
53:| Representantes y mandatos (Parlamento de Navarra) | ... | PARTIAL | Done now: NO. Blocker: ... `WAIVED_MISMATCH` ... Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --strict-network --timeout 30`. |
62:| Accion ejecutiva (Consejo de Ministros) | ... | PARTIAL | Done now: NO. Blocker: ... `WAIVED_MISMATCH` ... Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --strict-network --timeout 30`. |
11:- Done now: `NO` (`PARTIAL`).
12:- Current blocker: mismatch between tracker partial status and SQL done state for `moncloa_referencias` + `moncloa_rss_referencias`, now documented as temporary `WAIVED_MISMATCH` with policy artifact.
14:- Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --strict-network --timeout 30`.
17:- Done now: `NO` (`PARTIAL`).
18:- Current blocker: `403` en `--strict-network`; reproducible fallback en `--from-file`; mismatch currently waived via policy set.
20:- Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --strict-network --timeout 30`.
```

### G6

Command:
```bash
test -f docs/etl/sprints/AI-OPS-06/reports/mismatch-batch-prep.md && test -f docs/etl/sprints/AI-OPS-06/reports/mismatch-policy-apply-recompute.md && test -f docs/etl/sprints/AI-OPS-06/evidence/tracker-row-reconciliation.md && test -f docs/etl/sprints/AI-OPS-06/evidence/reconciliation-evidence-packet.md && echo "L1_ARTIFACTS_PRESENT=1"
rg -n "L1 = 16 pts|L1 task share = 4/8|Agent: L1 Mechanical Executor" docs/etl/sprints/AI-OPS-06/sprint-ai-agents.md
```

Output:
```text
L1_ARTIFACTS_PRESENT=1
29:- `L1 = 16 pts (59.3%)`
32:- `L1 task share = 4/8 (50%)`
200:4. Agent: L1 Mechanical Executor (5 pts)
252:5. Agent: L1 Mechanical Executor (5 pts)
304:6. Agent: L1 Mechanical Executor (3 pts)
356:7. Agent: L1 Mechanical Executor (3 pts)
```

## Carryover

No blocking carryover opened (`PASS`).

## Post-closeout watch item (non-gating)

| Owner | Watch item | Evidence | First command |
|---|---|---|---|
| L2 | Resolve temporary waivers before expiry (`2026-02-20`) by either tracker reconciliation or waiver renewal with L3 approval. | `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json`; `docs/etl/sprints/AI-OPS-06/reports/mismatch-policy-apply-recompute.md` | `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json --as-of-date 2026-02-20 --fail-on-mismatch --fail-on-done-zero-real` |
