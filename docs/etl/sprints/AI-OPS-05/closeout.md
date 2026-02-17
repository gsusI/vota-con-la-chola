# Sprint AI-OPS-05 Closeout

Date: 2026-02-16  
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Decision

**FAIL**

Reason: Gate `G5` is red (`etl-tracker-status mismatches = 3`).

## Gate Results

| Gate | Check | Result | Status |
|---|---|---|---|
| G1 | Data integrity (`fk check = 0`) | `fk_violations=0` | PASS |
| G2 | Queue health (`topic_evidence_reviews_pending = 0`) | `pending=0` | PASS |
| G3 | Signal/coverage guard (`declared_with_signal_pct >= kickoff baseline`) | baseline `0.3289902280130293`, current `0.3289902280130293` | PASS |
| G4 | Explainability visibility (Moncloa tracker status in explorer-sources payload) | `moncloa_referencias tracker_status=PARTIAL`, `moncloa_rss_referencias tracker_status=PARTIAL` | PASS |
| G5 | Tracker reconciliation (`etl-tracker-status mismatches = 0`) | `mismatches=3` | FAIL |
| G6 | Workload balance (L1 majority throughput evidence present) | `L1=14/25 pts (56.0%)`, L1 artifacts present | PASS |

## Evidence Commands and Outputs

### G1

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Output:
```text
0
```

### G2

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"
```

Output:
```text
0
```

### G3

Command:
```bash
python3 - <<'PY'
import json, sqlite3
from pathlib import Path
status=json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))
baseline=(status.get('analytics') or {}).get('evidence', {}).get('topic_evidence_declared_with_signal_pct')
conn=sqlite3.connect('etl/data/staging/politicos-es.db')
declared,signal=conn.execute(\"SELECT COUNT(*), SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) FROM topic_evidence WHERE evidence_type LIKE 'declared:%'\").fetchone()
conn.close()
current=(signal/declared) if declared else None
print('kickoff_baseline_declared_with_signal_pct', baseline)
print('current_declared_rows', declared)
print('current_declared_with_signal', signal)
print('current_declared_with_signal_pct', current)
print('not_lower_than_baseline', current is not None and baseline is not None and current >= baseline)
PY
```

Output:
```text
kickoff_baseline_declared_with_signal_pct 0.3289902280130293
current_declared_rows 614
current_declared_with_signal 202
current_declared_with_signal_pct 0.3289902280130293
not_lower_than_baseline True
```

### G4

Command:
```bash
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))
rows=[s for s in (obj.get('sources') or []) if isinstance(s,dict) and s.get('source_id') in ('moncloa_referencias','moncloa_rss_referencias')]
for r in sorted(rows, key=lambda x:x.get('source_id') or ''):
    tr=r.get('tracker') or {}
    print('source', r.get('source_id'), 'state', r.get('state'), 'tracker_status', tr.get('status'))
print('moncloa_rows_found', len(rows))
PY
```

Output:
```text
source moncloa_referencias state ok tracker_status PARTIAL
source moncloa_rss_referencias state ok tracker_status PARTIAL
moncloa_rows_found 2
```

### G5

Command:
```bash
just etl-tracker-status | rg "moncloa_referencias|moncloa_rss_referencias|parlamento_navarra_parlamentarios_forales|mismatches:|done_zero_real:"
```

Output:
```text
moncloa_referencias                       | PARTIAL   | DONE    | 7/8           | 2       | 20      | 20          | 2/5                  | MISMATCH
moncloa_rss_referencias                   | PARTIAL   | DONE    | 8/10          | 8       | 8       | 8           | 2/6                  | MISMATCH
parlamento_navarra_parlamentarios_forales | PARTIAL   | DONE    | 3/8           | 50      | 50      | 50          | 1/2                  | MISMATCH
mismatches: 3
done_zero_real: 0
```

### G6

Command:
```bash
rg -n "L1 = 14 pts|L1 task share = 4/8" docs/etl/sprints/AI-OPS-05/sprint-ai-agents.md
```

Output:
```text
27:- `L1 = 14 pts (56.0%)`
30:- `L1 task share = 4/8 (50%)`
```

Command:
```bash
for f in docs/etl/sprints/AI-OPS-05/reports/probe-batch-prep.md docs/etl/sprints/AI-OPS-05/reports/moncloa-apply-recompute.md docs/etl/sprints/AI-OPS-05/reports/navarra-galicia-blocker-refresh.md docs/etl/sprints/AI-OPS-05/evidence/tracker-reconciliation.md; do if [ -f "$f" ]; then echo "ok|$f"; else echo "missing|$f"; fi; done
```

Output:
```text
ok|docs/etl/sprints/AI-OPS-05/reports/probe-batch-prep.md
ok|docs/etl/sprints/AI-OPS-05/reports/moncloa-apply-recompute.md
ok|docs/etl/sprints/AI-OPS-05/reports/navarra-galicia-blocker-refresh.md
ok|docs/etl/sprints/AI-OPS-05/evidence/tracker-reconciliation.md
```

## Carryover (opened due FAIL)

| Owner | Carryover task | Blocker evidence | First command |
|---|---|---|---|
| L2 | Reconcile Moncloa + Navarra tracker-vs-sql contract to eliminate `mismatches` (currently 3) without hiding blocked semantics. | `docs/etl/sprints/AI-OPS-05/evidence/tracker-reconciliation.md`; `just etl-tracker-status` output (`mismatches: 3`). | `just etl-tracker-status` |
| L3 | Approve/deny scoped allowlist strategy for unresolved blocked volatility in strict gate path (`fail-on-mismatch`) before changing gate semantics. | `docs/etl/sprints/AI-OPS-05/reports/tracker-gate-hardening.md` (allowlist proposal). | `sed -n '1,220p' docs/etl/sprints/AI-OPS-05/reports/tracker-gate-hardening.md` |
| L1 | Run fresh strict-network probes for blocked/autonomico rows and attach evidence deltas to keep blocker status current. | Current tracker rows remain `PARTIAL` with explicit blocked notes in `docs/etl/e2e-scrape-load-tracker.md`. | `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --strict-network --timeout 30` |

