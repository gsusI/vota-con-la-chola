# AI-OPS-06 - mismatch-policy dashboard visibility

## objective
Expose mismatch-policy transparency in explorer-sources payload so operations can distinguish waived vs unwaived reconciliation drift.

## implementation
- Updated `scripts/graph_ui_server.py` to add source-level fields:
  - `mismatch_state`
  - `mismatch_waived`
  - `waiver_expiry`
- Kept payload backward-compatible by preserving existing keys and adding defaults:
  - `UNTRACKED` / `false` / `""` when tracker row is missing.
- Reused waiver contract parsing from `scripts/e2e_tracker_status.py` via `docs/etl/mismatch-waivers.json`.
- Added focused regression test:
  - `tests/test_graph_ui_server_mismatch_payload.py`

## mismatch-state rules
- `UNTRACKED`: no mapped tracker row for the source.
- `DONE_ZERO_REAL`: tracker `DONE` but no reproducible network load evidence.
- `WAIVED_MISMATCH`: tracker/sql status differs and active waiver exists.
- `MISMATCH`: tracker/sql status differs without active waiver (including expired waiver).
- `MATCH`: tracker/sql status agrees.

## payload diff sample
```diff
 {
   "source_id": "moncloa_referencias",
   "tracker": {"status": "PARTIAL"},
   "sql_status": "DONE",
+  "mismatch_state": "MISMATCH",
+  "mismatch_waived": false,
+  "waiver_expiry": ""
 }
```

## evidence commands and outputs

### 1) tests
```bash
python3 -m unittest tests.test_graph_ui_server_mismatch_payload
python3 -m unittest tests.test_graph_ui_server_tracker_mapping
```

Observed:
- `Ran 1 test ... OK`
- `Ran 2 tests ... OK`

### 2) export snapshot
```bash
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out /tmp/aiops06-status.json
```

Observed:
- `OK sources status snapshot -> /tmp/aiops06-status.json`

### 3) inspect Moncloa payload row
```bash
jq '.sources[] | select(.source_id=="moncloa_referencias") | {source_id, tracker: .tracker.status, sql_status, mismatch_state, mismatch_waived, waiver_expiry}' /tmp/aiops06-status.json
```

Observed:
```json
{
  "source_id": "moncloa_referencias",
  "tracker": "PARTIAL",
  "sql_status": "DONE",
  "mismatch_state": "MISMATCH",
  "mismatch_waived": false,
  "waiver_expiry": ""
}
```

## compatibility note
No existing payload keys were removed or renamed. New fields are additive and safe for current explorer consumers.
