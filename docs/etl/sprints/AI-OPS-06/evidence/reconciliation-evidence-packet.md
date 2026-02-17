# AI-OPS-06 final reconciliation evidence packet

## Execution date
- 2026-02-16

## Command list and logs
1. Refresh explorer sources snapshot
```bash
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
```
- Log: `docs/etl/sprints/AI-OPS-06/evidence/reconciliation-snapshot-refresh.log`
- Log excerpt: `OK sources status snapshot -> docs/gh-pages/explorer-sources/data/status.json`

2. Snapshot summary validation
```bash
jq '.summary.sql,.summary.tracker' docs/gh-pages/explorer-sources/data/status.json
```
- Log: `docs/etl/sprints/AI-OPS-06/evidence/reconciliation-summary-jq.log`
- Summary output:
  - `.summary.sql = {"todo": 0, "partial": 1, "done": 31, "foreign_key_violations": 0}`
  - `.summary.tracker = {"items_total": 54, "unmapped": 26, "todo": 20, "partial": 5, "done": 29, "mismatch": 3, "waived_mismatch": 0, "done_zero_real": 0, "untracked_sources": 2, "waivers_active": 0, "waivers_expired": 0, "waivers_error": ""}`

3. Mismatch source parity check against checker candidate inputs
```bash
python3 - <<'PY'
import csv
import json
from pathlib import Path
status = json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text())['sources']
status_map = {s['source_id']: s for s in status}
rows = list(csv.DictReader(Path('docs/etl/sprints/AI-OPS-06/exports/mismatch_candidates.csv').open())
source_ids = ['moncloa_referencias', 'moncloa_rss_referencias', 'parlamento_navarra_parlamentarios_forales']
print('PARITY_CHECK_SOURCE_START')
for sid in source_ids:
    s = status_map[sid]
    ref = next(r for r in rows if r['source_id'] == sid)
    ok = (s['tracker']['status'] == ref['checklist_status'] and s['sql_status'] == ref['sql_status'] and s['mismatch_state'] == 'MISMATCH')
    print(f"{sid}: tracker={s['tracker']['status']} sql={s['sql_status']} mismatch_state={s['mismatch_state']} waived={s['mismatch_waived']} checker={ref['checklist_status']}/{ref['sql_status']} result={"PASS" if ok else "FIELD_MISMATCH"}")
print('PARITY_CHECK_SOURCE_END')
PY
```
- Log: `docs/etl/sprints/AI-OPS-06/evidence/reconciliation-parity-check.log`
- Result: all mismatch-source rows PASS parity against checker inputs.

4. Gate exit summary extraction (for strict pass/fail proof)
```bash
for f in docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-baseline-check.log docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-explicit-mismatch-fail.log docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-strict-gate.log docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-apply-legacy-gate.log; do rg -n "FAIL:|mismatches:|waived_mismatches:|waivers_active:|done_zero_real:|EXIT_CODE:" "$f"; done
```
- Log: `docs/etl/sprints/AI-OPS-06/evidence/reconciliation-gate-exit-codes.log`

## final mismatches and gate exit code
- final mismatches (explicit waiver mode): `0`
- final waived_mismatches (explicit waiver mode): `3`
- final gate exit code map:
  - strict gate (`just etl-tracker-gate`): `1`
  - baseline checker run (`python3 scripts/e2e_tracker_status.py --db ... --tracker ...`): `0`
  - explicit mismatch-fail run (`--waivers ... --fail-on-mismatch --fail-on-done-zero-real`): `0`
  - legacy gate (`just etl-tracker-gate-legacy`): `0`

## Parity matrix (dashboard payload vs checker payload)
- Source: `source_id=moncloa_referencias`
  - status.json: `tracker=PARTIAL`, `sql=DONE`, `mismatch_state=MISMATCH`, `mismatch_waived=False`
  - checker row: `checklist_status=PARTIAL`, `sql_status=DONE`
  - parity: PASS
- Source: `source_id=moncloa_rss_referencias`
  - status.json: `tracker=PARTIAL`, `sql=DONE`, `mismatch_state=MISMATCH`, `mismatch_waived=False`
  - checker row: `checklist_status=PARTIAL`, `sql_status=DONE`
  - parity: PASS
- Source: `source_id=parlamento_navarra_parlamentarios_forales`
  - status.json: `tracker=PARTIAL`, `sql=DONE`, `mismatch_state=MISMATCH`, `mismatch_waived=False`
  - checker row: `checklist_status=PARTIAL`, `sql_status=DONE`
  - parity: PASS

## escalation condition check
- strict gate still fails on unwaived mismatch state (expected by policy), with source IDs:
  - `moncloa_referencias`
  - `moncloa_rss_referencias`
  - `parlamento_navarra_parlamentarios_forales`
- No field-level divergence was found between snapshot payload and mismatch_candidates for these sources.
- Evidence references:
  - `docs/etl/sprints/AI-OPS-06/reports/mismatch-policy-apply-recompute.md`
  - `docs/etl/sprints/AI-OPS-06/evidence/tracker-row-reconciliation.md`
  - `docs/etl/sprints/AI-OPS-06/evidence/reconciliation-parity-check.log`
  - `docs/etl/sprints/AI-OPS-06/evidence/reconciliation-gate-exit-codes.log`
