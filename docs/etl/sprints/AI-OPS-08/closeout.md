# AI-OPS-08 Closeout

Date: 2026-02-16  
Repository: `REPO_ROOT/vota-con-la-chola`

## Project framing

AI-OPS-08 focused on tracker-contract reconciliation and strict mismatch-policy hardening. The sprint closes with BOE fully reconciled (`DONE/DONE`), Moncloa stable in `MATCH`, canonical waiver registry in place, and strict gate green without waivers.

## Gate evaluation (G1-G6)

| Gate | Condition | Evidence command(s) | Observed | Result |
|---|---|---|---|---|
| G1 data integrity | `fk_violations=0` | `sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"` | `fk_violations=0` | PASS |
| G2 queue health | `topic_evidence_reviews_pending=0` | `sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"` | `topic_evidence_reviews_pending=0` | PASS |
| G3 tracker-contract alignment | `boe_api_legal` is not `UNTRACKED` and Moncloa rows remain `MATCH` | `python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json` + payload summary script | `boe_api_legal: MATCH / DONE / DONE`, `moncloa_referencias: MATCH`, `moncloa_rss_referencias: MATCH` | PASS |
| G4 strict-policy behavior | unwaived `mismatches=0`, `waivers_expired=0`, `done_zero_real=0` | `just etl-tracker-gate` | `strict_exit=0`, `mismatches=0`, `waivers_expired=0`, `done_zero_real=0` | PASS |
| G5 waiver burn-down | active waivers not increased vs kickoff and Navarra waiver reduced to `0` | kickoff baseline in `docs/etl/sprints/AI-OPS-08/kickoff.md` + `python3 - <<'PY' ... docs/etl/mismatch-waivers.json ... PY` | kickoff `waivers_active=1`; current `waivers_total=0`, `navarra_waivers=0` | PASS |
| G6 workload balance | L1 majority throughput evidence present | `test -f` for L1 artifacts (`waiver-burndown-batch-prep.md`, `waiver-burndown-apply-recompute.md`, `tracker-row-reconciliation.md`, `reconciliation-evidence-packet.md`, `waiver_burndown_candidates.csv`, `tracker_contract_candidates.csv`) | `l1_artifacts_present=6/6` | PASS |

## Command evidence snapshots

### 1) G1/G2 SQL checks

Commands:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"
```

Output:
```text
fk_violations=0
topic_evidence_reviews_pending=0
```

### 2) G3 payload alignment check

Commands:
```bash
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))
for sid in ('boe_api_legal','moncloa_referencias','moncloa_rss_referencias','parlamento_navarra_parlamentarios_forales'):
    row=next((x for x in obj.get('sources',[]) if x.get('source_id')==sid),None)
    print(sid, (row or {}).get('mismatch_state'), (row or {}).get('tracker',{}).get('status'), (row or {}).get('sql_status'))
PY
```

Output:
```text
boe_api_legal MATCH DONE DONE
moncloa_referencias MATCH DONE DONE
moncloa_rss_referencias MATCH DONE DONE
parlamento_navarra_parlamentarios_forales MATCH PARTIAL PARTIAL
```

### 3) G4 strict-policy check

Commands:
```bash
just etl-tracker-gate
```

Output excerpt:
```text
strict_exit=0
boe_api_legal ... OK
parlamento_navarra_parlamentarios_forales ... OK
mismatches: 0
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
```

### 4) G5 waiver burn-down check

Commands:
```bash
rg -n "waivers_active =" docs/etl/sprints/AI-OPS-08/kickoff.md
python3 - <<'PY'
import json
from pathlib import Path
w=json.loads(Path('docs/etl/mismatch-waivers.json').read_text(encoding='utf-8'))
rows=w.get('waivers',[])
nav=[x for x in rows if x.get('source_id')=='parlamento_navarra_parlamentarios_forales']
print('waivers_total',len(rows))
print('navarra_waivers',len(nav))
PY
```

Output:
```text
kickoff: waivers_active = 1
waivers_total 0
navarra_waivers 0
```

### 5) G6 L1 throughput evidence

Command:
```bash
test -f docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-batch-prep.md && \
test -f docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md && \
test -f docs/etl/sprints/AI-OPS-08/evidence/tracker-row-reconciliation.md && \
test -f docs/etl/sprints/AI-OPS-08/evidence/reconciliation-evidence-packet.md && \
test -f docs/etl/sprints/AI-OPS-08/exports/waiver_burndown_candidates.csv && \
test -f docs/etl/sprints/AI-OPS-08/exports/tracker_contract_candidates.csv && \
echo "l1_artifacts_present=6/6"
```

Output:
```text
l1_artifacts_present=6/6
```

## Decision

**AI-OPS-08 = PASS**

All mandatory gates `G1..G6` are green in the same evidence set.

## Carryover

No mandatory carryover opened from AI-OPS-08 closeout.

Operational watch items (non-blocking):
- Keep Galicia row `PARTIAL` with strict-network blocker evidence until reproducible network path is available.
- Continue Tier-1 backlog execution from tracker rows still in `PARTIAL/TODO`.
