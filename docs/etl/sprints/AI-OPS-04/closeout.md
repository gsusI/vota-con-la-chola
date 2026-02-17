# Sprint AI-OPS-04 Closeout

Date: 2026-02-16  
Repository: `REPO_ROOT/vota-con-la-chola`  
Sprint: `AI-OPS-04` (Moncloa critical-path slice)

## Decision

**FAIL**

Reason: one mandatory gate is still red (`tracker row reconciled with evidence + blocker + next command`).

## Gate Table

| Gate | Check | Result | Status |
|---|---|---|---|
| G1 | FK check = 0 | `fk_violations=0` | PASS |
| G2 | Moncloa sources ingested in at least one reproducible mode | `moncloa_runs_from_file_loaded=5` | PASS |
| G3 | `policy_events` from Moncloa > 0 with traceability fields populated | `28` events, traceability `28/28/28/28` | PASS |
| G4 | Tracker row reconciled with evidence + blocker + next command | Row remains `TODO` in tracker | FAIL |
| G5 | L1 delivered majority throughput work | L1 planned at `61.3%` and L1 artifacts present | PASS |

## Evidence Commands and Outputs

### G1 - FK Integrity (PASS)

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Output:
```text
0
```

### G2 - Reproducible Moncloa Ingest (PASS)

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS moncloa_runs_from_file_loaded FROM ingestion_runs WHERE source_id LIKE 'moncloa_%' AND records_loaded>0 AND raw_path IS NOT NULL AND trim(raw_path)<>'';"
```

Output:
```text
5
```

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, records_loaded FROM ingestion_runs WHERE source_id LIKE 'moncloa_%' ORDER BY run_id DESC LIMIT 6;"
```

Output:
```text
moncloa_rss_referencias|4
moncloa_rss_referencias|8
moncloa_referencias|20
moncloa_rss_referencias|4
moncloa_rss_referencias|0
moncloa_referencias|3
```

### G3 - Moncloa `policy_events` + Traceability (PASS)

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) AS policy_events_total FROM policy_events WHERE source_id LIKE 'moncloa_%' GROUP BY source_id ORDER BY source_id;"
```

Output:
```text
moncloa_referencias|20
moncloa_rss_referencias|8
```

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS moncloa_policy_events_total, SUM(CASE WHEN source_url IS NOT NULL AND trim(source_url)<>'' THEN 1 ELSE 0 END) AS with_source_url, SUM(CASE WHEN source_record_pk IS NOT NULL THEN 1 ELSE 0 END) AS with_source_record_pk, SUM(CASE WHEN raw_payload IS NOT NULL AND trim(raw_payload)<>'' THEN 1 ELSE 0 END) AS with_raw_payload, SUM(CASE WHEN source_snapshot_date IS NOT NULL AND trim(source_snapshot_date)<>'' THEN 1 ELSE 0 END) AS with_snapshot_date FROM policy_events WHERE source_id LIKE 'moncloa_%';"
```

Output:
```text
28|28|28|28|28
```

### G4 - Tracker Reconciliation (FAIL)

Command:
```bash
rg -n "Accion ejecutiva \(Consejo de Ministros\)" docs/etl/e2e-scrape-load-tracker.md
```

Output:
```text
61:| Accion ejecutiva (Consejo de Ministros) | Ejecutivo | La Moncloa: referencias + RSS | TODO | Scraper + normalizacion; validar acuerdos y normas contra BOE cuando exista publicacion |
```

Evidence exists but not applied to tracker row:
- `docs/etl/sprints/AI-OPS-04/evidence/moncloa-tracker-evidence.md`
- `docs/etl/sprints/AI-OPS-04/reports/moncloa-tracker-row-draft.md`

### G5 - L1 Majority Throughput (PASS)

Command:
```bash
rg -n "L1 = 19 pts|L1 task share = 6/10" docs/etl/sprints/AI-OPS-04/sprint-ai-agents.md
```

Output:
```text
25:- `L1 = 19 pts (61.3%)`
28:- `L1 task share = 6/10 (60%)`
```

Command:
```bash
for f in docs/etl/sprints/AI-OPS-04/reports/moncloa-batch-prep.md docs/etl/sprints/AI-OPS-04/reports/moncloa-contract-catalog.md docs/etl/sprints/AI-OPS-04/reports/moncloa-ingest-matrix.md docs/etl/sprints/AI-OPS-04/reports/moncloa-apply-recompute.md docs/etl/sprints/AI-OPS-04/reports/moncloa-dashboard-parity.md docs/etl/sprints/AI-OPS-04/evidence/moncloa-tracker-evidence.md docs/etl/sprints/AI-OPS-04/reports/moncloa-tracker-row-draft.md; do if [ -f "$f" ]; then echo "ok|$f"; else echo "missing|$f"; fi; done
```

Output:
```text
ok|docs/etl/sprints/AI-OPS-04/reports/moncloa-batch-prep.md
ok|docs/etl/sprints/AI-OPS-04/reports/moncloa-contract-catalog.md
ok|docs/etl/sprints/AI-OPS-04/reports/moncloa-ingest-matrix.md
ok|docs/etl/sprints/AI-OPS-04/reports/moncloa-apply-recompute.md
ok|docs/etl/sprints/AI-OPS-04/reports/moncloa-dashboard-parity.md
ok|docs/etl/sprints/AI-OPS-04/evidence/moncloa-tracker-evidence.md
ok|docs/etl/sprints/AI-OPS-04/reports/moncloa-tracker-row-draft.md
```

## Carryover (opened because FAIL)

1. Owner `L2` - Reconcile tracker row in `docs/etl/e2e-scrape-load-tracker.md` to `PARTIAL` using the approved draft wording (done + blocker + one next command).
First command:
```bash
rg -n "Accion ejecutiva \(Consejo de Ministros\)" docs/etl/e2e-scrape-load-tracker.md
```

2. Owner `L1` - Run strict-network probe to keep blocker evidence fresh before AI-OPS-05 kickoff.
First command:
```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --strict-network --timeout 30
```

3. Owner `L3` - Re-run closeout once carryover 1 is merged; promote to PASS only if all gates are green.
First command:
```bash
test -f docs/etl/sprints/AI-OPS-04/closeout.md && rg -n "G4|Decision|FAIL|PASS" docs/etl/sprints/AI-OPS-04/closeout.md
```
