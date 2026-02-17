# AI-OPS-08 BOE Tracker Mapping Hardening

Date: 2026-02-16
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Objective

Remove BOE tracker drift by mapping `Marco legal electoral` deterministically to `boe_api_legal` in both the checker and explorer payload path.

## Implemented changes

1) Deterministic BOE mapping in checker
- File: `scripts/e2e_tracker_status.py`
- Added row-level mapping contract:
  - `TRACKER_TIPO_SOURCE_HINTS["Marco legal electoral"] = ["boe_api_legal"]`
- Added BOE fuentes hint fallback:
  - `"BOE API": ["boe_api_legal"]`
- Added `_infer_tracker_source_ids(tipo_dato, fuente)` and switched parser to use it.
- Mapping precedence is now deterministic and documented in code comments:
  - row label mapping first,
  - fuentes hint second.

2) Deterministic BOE mapping in explorer payload path
- File: `scripts/graph_ui_server.py`
- Added same row-level + fuentes mapping entries.
- Extended `_infer_tracker_source_ids(..., tipo_dato="")` with row-first precedence.
- Updated tracker row parsing to pass `tipo_dato` into inference.

## Focused tests added/updated

1) Checker mapping test
- File: `tests/test_e2e_tracker_status_tracker.py`
- Added:
  - `test_parse_tracker_rows_maps_marco_legal_electoral_to_boe_source_id`

2) Graph mapping + payload visibility tests
- File: `tests/test_graph_ui_server_tracker_mapping.py`
- Added:
  - `test_infer_tracker_source_ids_maps_marco_legal_to_boe_source`
  - `test_load_tracker_items_sets_boe_source_ids`
  - `test_boe_payload_exposes_tracker_and_mismatch_fields_after_mapping`

## Validation commands and results

### A) Tests

Command:
```bash
python3 -m unittest discover -s tests -p 'test*tracker*py'
```
Result:
```text
Ran 13 tests ...
OK
```

Command:
```bash
python3 -m unittest discover -s tests -p 'test*graph*tracker*py'
```
Result:
```text
Ran 5 tests ...
OK
```

### B) Checker output now tracks BOE row

Command:
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md | rg -n "boe_api_legal|tracker_sources|mismatches|moncloa_referencias|moncloa_rss_referencias"
```

Output:
```text
8:boe_api_legal                             | PARTIAL   | DONE    | ... | MISMATCH
21:moncloa_referencias                       | DONE      | DONE    | ... | OK
22:moncloa_rss_referencias                   | DONE      | DONE    | ... | OK
37:tracker_sources: 28
39:mismatches: 2
40:waived_mismatches: 0
```

### C) Payload field visibility after mapping

Command:
```bash
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out /tmp/aiops08-status.json
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('/tmp/aiops08-status.json').read_text(encoding='utf-8'))
for sid in ('boe_api_legal','moncloa_referencias','moncloa_rss_referencias','parlamento_navarra_parlamentarios_forales'):
    row=next((x for x in obj.get('sources',[]) if x.get('source_id')==sid),None)
    print(sid, {
      'tracker_status': (row.get('tracker') or {}).get('status',''),
      'sql_status': row.get('sql_status',''),
      'mismatch_state': row.get('mismatch_state',''),
      'mismatch_waived': row.get('mismatch_waived',False),
      'waiver_expiry': row.get('waiver_expiry','')
    })
PY
```

Output:
```text
boe_api_legal {'tracker_status': 'PARTIAL', 'sql_status': 'DONE', 'mismatch_state': 'MISMATCH', 'mismatch_waived': False, 'waiver_expiry': ''}
moncloa_referencias {'tracker_status': 'DONE', 'sql_status': 'DONE', 'mismatch_state': 'MATCH', 'mismatch_waived': False, 'waiver_expiry': ''}
moncloa_rss_referencias {'tracker_status': 'DONE', 'sql_status': 'DONE', 'mismatch_state': 'MATCH', 'mismatch_waived': False, 'waiver_expiry': ''}
parlamento_navarra_parlamentarios_forales {'tracker_status': 'PARTIAL', 'sql_status': 'DONE', 'mismatch_state': 'MISMATCH', 'mismatch_waived': False, 'waiver_expiry': ''}
```

## Before/after mismatch snapshot

| Snapshot | tracker_sources | mismatches | boe_api_legal tracker_status | boe_api_legal mismatch_state | moncloa_referencias | moncloa_rss_referencias |
|---|---:|---:|---|---|---|---|
| Before (AI-OPS-08 kickoff baseline) | 27 | 1 | `` (unmapped) | `UNTRACKED` | `MATCH` | `MATCH` |
| After (this implementation) | 28 | 2 | `PARTIAL` | `MISMATCH` | `MATCH` | `MATCH` |

Interpretation:
- The BOE row is no longer hidden as `UNTRACKED`; it is now explicitly reconciled (`PARTIAL` vs SQL `DONE`).
- Mismatch count increases by 1 because BOE is now correctly part of reconciliation scope.
- No regression on Moncloa rows: both remain `MATCH`.

## Notes for next step

- To drive `mismatches` back down, the tracker row `Marco legal electoral` must be reconciled with current SQL truth (`DONE`) only after the documented DoD evidence path is accepted.
