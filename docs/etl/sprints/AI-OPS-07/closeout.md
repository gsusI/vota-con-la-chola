# AI-OPS-07 Closeout

Date: 2026-02-16  
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Project framing

AI-OPS-07 focused on Moncloa-BOE dual-entry readiness with strict mismatch-policy auditability. The sprint now closes with BOE integrated in `policy_events`, Moncloa tracker reconciliation applied, and Moncloa waiver dependency removed.

## Gate evaluation (G1-G6)

| Gate | Condition | Evidence command(s) | Observed | Result |
|---|---|---|---|---|
| G1 data integrity | `fk_violations=0` | `sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"` | `fk_violations=0` | PASS |
| G2 queue health | `topic_evidence_reviews_pending=0` | `sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"` | `topic_evidence_reviews_pending=0` | PASS |
| G3 BOE integration | `policy_events_boe > 0` with traceability fields populated | `sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_boe FROM policy_events WHERE source_id LIKE 'boe_%';"` + `sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS boe_traceability_full FROM policy_events WHERE source_id LIKE 'boe_%' AND source_url IS NOT NULL AND trim(source_url)<>'' AND source_record_pk IS NOT NULL AND raw_payload IS NOT NULL AND trim(raw_payload)<>'' AND source_snapshot_date IS NOT NULL AND trim(source_snapshot_date)<>'';"` | `policy_events_boe=298`, `boe_traceability_full=298` | PASS |
| G4 dual-entry progress | Moncloa corroboration evidence exists and `unwaived mismatches=0` | `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/sprints/AI-OPS-07/evidence/mismatch-policy-applied.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real` + `docs/etl/sprints/AI-OPS-07/exports/moncloa_boe_reconciliation_candidates.csv` | checker `mismatches=0` and dual-entry artifact present (`candidates_total=10`) | PASS |
| G5 waiver governance | no expired waivers; active waivers not increased vs kickoff; Moncloa waiver count reduced to `0` | Kickoff baseline (`docs/etl/sprints/AI-OPS-07/kickoff.md`: `waivers_active=3`, `waivers_expired=0`) + waiver-aware checker with `docs/etl/sprints/AI-OPS-07/evidence/mismatch-policy-applied.json` + tracker row `Accion ejecutiva (Consejo de Ministros)` now `DONE` | Current: `waivers_active=1`, `waivers_expired=0`, `moncloa_waived_mismatches=0` | PASS |
| G6 workload balance | L1 majority throughput evidence present | `test -f` on L1 artifacts: `docs/etl/sprints/AI-OPS-07/reports/dual-entry-batch-prep.md`, `docs/etl/sprints/AI-OPS-07/reports/dual-entry-apply-recompute.md`, `docs/etl/sprints/AI-OPS-07/evidence/tracker-row-reconciliation.md`, `docs/etl/sprints/AI-OPS-07/evidence/reconciliation-evidence-packet.md`, `docs/etl/sprints/AI-OPS-07/exports/moncloa_boe_reconciliation_candidates.csv`, `docs/etl/sprints/AI-OPS-07/exports/waiver_burndown_candidates.csv` | `l1_artifacts_present=6/6` | PASS |

## Command evidence snapshots

### 1) Waiver-aware strict check (policy-consistent)

Command:
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/sprints/AI-OPS-07/evidence/mismatch-policy-applied.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real
```

Relevant output:
```text
moncloa_referencias                       | DONE      | DONE    | ... | OK
moncloa_rss_referencias                   | DONE      | DONE    | ... | OK
parlamento_navarra_parlamentarios_forales | PARTIAL   | DONE    | ... | WAIVED_MISMATCH
mismatches: 0
waived_mismatches: 1
waivers_active: 1
waivers_expired: 0
done_zero_real: 0
```

### 2) G1/G2/G3 SQL checks

Commands:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_boe FROM policy_events WHERE source_id LIKE 'boe_%';"
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS boe_traceability_full FROM policy_events WHERE source_id LIKE 'boe_%' AND source_url IS NOT NULL AND trim(source_url)<>'' AND source_record_pk IS NOT NULL AND raw_payload IS NOT NULL AND trim(raw_payload)<>'' AND source_snapshot_date IS NOT NULL AND trim(source_snapshot_date)<>'';"
```

Output:
```text
fk_violations=0
topic_evidence_reviews_pending=0
policy_events_boe=298
boe_traceability_full=298
```

### 3) Dashboard parity for Moncloa tracker reconciliation

Command:
```bash
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
python3 - <<'PY'
import json
from pathlib import Path
obj = json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))
for sid in ('moncloa_referencias','moncloa_rss_referencias'):
    row = next(s for s in obj['sources'] if s['source_id'] == sid)
    print(sid, row['tracker']['status'], row['sql_status'], row['mismatch_state'])
PY
```

Output:
```text
OK sources status snapshot -> docs/gh-pages/explorer-sources/data/status.json
moncloa_referencias DONE DONE MATCH
moncloa_rss_referencias DONE DONE MATCH
```

## Decision

**AI-OPS-07 = PASS**

All mandatory gates `G1..G6` are green under the sprint policy contract.

## Carryover

No mandatory carryover opened from AI-OPS-07 closeout.  
Operational watch item (non-blocking): keep Navarra waiver under expiry control (`expires_on=2026-02-20`) until its strict-network blocker is resolved.
