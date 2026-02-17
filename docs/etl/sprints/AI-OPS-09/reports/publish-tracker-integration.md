# AI-OPS-09 - Publish/Tracker Integration (New Source Families)

## Scope
- Integrate new source families into tracker reconciliation and published status payload:
  - `placsp_sindicacion`
  - `placsp_autonomico`
  - `bdns_api_subvenciones`
  - `bdns_autonomico`
  - `eurostat_sdmx`
  - `bde_series_api`
  - `aemet_opendata_series`
- Keep JSON payload backward-compatible (no key removals).

## Changes
- `scripts/graph_ui_server.py`
  - Extended `TRACKER_TIPO_SOURCE_HINTS` with explicit AI-OPS-09 row mappings.
  - Extended `TRACKER_SOURCE_HINTS` fallback mappings for PLACSP/BDNS/Eurostat/BDE/AEMET.
  - Result: new sources are no longer `UNTRACKED` when tracker rows exist.
- `tests/test_graph_ui_server_tracker_mapping.py`
  - Added mapping coverage test for money/outcomes rows.
  - Added payload test to assert `tracker.status`, `sql_status`, `mismatch_state`, `mismatch_waived`, `waiver_expiry`.
- `tests/test_e2e_tracker_status_tracker.py`
  - Added focused fallback-hint mapping test for PLACSP/BDNS/Eurostat/BDE/AEMET in tracker checker.

## Before/After Mismatch Snapshot

Command used (pre-fix capture):
```bash
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out /tmp/aiops09-status.json
```

Pre-fix observed rows (captured in this sprint before patch):
```text
placsp_sindicacion|tracker=|sql=PARTIAL|mismatch=UNTRACKED
placsp_autonomico|tracker=|sql=TODO|mismatch=UNTRACKED
bdns_api_subvenciones|tracker=|sql=PARTIAL|mismatch=UNTRACKED
bdns_autonomico|tracker=|sql=TODO|mismatch=UNTRACKED
eurostat_sdmx|tracker=|sql=PARTIAL|mismatch=UNTRACKED
bde_series_api|tracker=|sql=PARTIAL|mismatch=UNTRACKED
aemet_opendata_series|tracker=|sql=PARTIAL|mismatch=UNTRACKED
```

Command used (post-fix):
```bash
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out dist/status-aiops09-after.json
python3 - <<'PY'
import json
p=json.load(open('dist/status-aiops09-after.json'))
ids=['placsp_sindicacion','placsp_autonomico','bdns_api_subvenciones','bdns_autonomico','eurostat_sdmx','bde_series_api','aemet_opendata_series']
by={s['source_id']:s for s in p.get('sources',[])}
for sid in ids:
    s=by.get(sid); tr=s.get('tracker',{})
    print(f"{sid}|tracker={tr.get('status','')}|sql={s.get('sql_status','')}|mismatch={s.get('mismatch_state','')}|waived={s.get('mismatch_waived','')}|expiry={s.get('waiver_expiry','')}")
PY
```

Post-fix output:
```text
placsp_sindicacion|tracker=TODO|sql=PARTIAL|mismatch=MISMATCH|waived=False|expiry=
placsp_autonomico|tracker=TODO|sql=TODO|mismatch=MATCH|waived=False|expiry=
bdns_api_subvenciones|tracker=TODO|sql=PARTIAL|mismatch=MISMATCH|waived=False|expiry=
bdns_autonomico|tracker=TODO|sql=TODO|mismatch=MATCH|waived=False|expiry=
eurostat_sdmx|tracker=TODO|sql=PARTIAL|mismatch=MISMATCH|waived=False|expiry=
bde_series_api|tracker=TODO|sql=PARTIAL|mismatch=MISMATCH|waived=False|expiry=
aemet_opendata_series|tracker=TODO|sql=PARTIAL|mismatch=MISMATCH|waived=False|expiry=
```

## Regression Checks

### Tracker tests
Command:
```bash
python3 -m unittest discover -s tests -p 'test*tracker*py'
```
Result:
```text
Ran 18 tests in 0.092s
OK
```

### Graph tests
Command:
```bash
python3 -m unittest discover -s tests -p 'test*graph*py'
```
Result:
```text
Ran 11 tests in 1.814s
OK
```

## Compatibility Note
- JSON shape remains backward-compatible:
  - existing keys preserved (`tracker`, `sql_status`, `mismatch_state`, `mismatch_waived`, `waiver_expiry`).
  - only mapping coverage was expanded so rows now resolve to tracked source IDs.
