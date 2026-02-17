# AI-OPS-05 Tracker Contract Hardening

Date: 2026-02-16  
Repository: `REPO_ROOT/vota-con-la-chola`

## Objective

Harden tracker/source mapping and blocked-aware status semantics so `e2e_tracker_status` and dashboard mapping reflect current operational truth.

## Code changes

1. `scripts/e2e_tracker_status.py`
- Added tracker hint mapping for Moncloa row:
  - `La Moncloa: referencias + RSS` -> `moncloa_referencias`, `moncloa_rss_referencias`
- Added deterministic blocked parser:
  - explicit `"bloquead*"` detection from tracker `Bloque principal`.
- Added blocked-aware SQL status guard:
  - if row is explicitly blocked, `last_loaded=0`, and `max_loaded_network>0`, force `sql=PARTIAL` (do not auto-promote to `DONE` from historical max only).

2. `scripts/graph_ui_server.py`
- Added same Moncloa tracker hint mapping for dashboard/tracker join.
- Added same blocked-note detector and applied blocked-aware status derivation in sources payload.

3. Tests
- `tests/test_e2e_tracker_status_tracker.py`
  - Moncloa row mapping to both source_ids.
  - Navarra blocked-row status behavior (`DONE -> PARTIAL` under blocked guard with `last_loaded=0`).
- `tests/test_graph_ui_server_tracker_mapping.py`
  - Moncloa mapping via `_infer_tracker_source_ids`.
  - `load_tracker_items` includes both Moncloa source_ids.

## Before/After mismatch table

Command:
```bash
python3 - <<'PY'
from pathlib import Path
from scripts import e2e_tracker_status as m

tracker_path = Path('docs/etl/e2e-scrape-load-tracker.md')
db_path = Path('etl/data/staging/politicos-es.db')
rows_new = m.parse_tracker_rows(tracker_path)
legacy_hints = {k: v for k, v in m.TRACKER_SOURCE_HINTS.items() if k != 'La Moncloa: referencias + RSS'}

header = '| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |'
legacy_rows = {}
lines = tracker_path.read_text(encoding='utf-8').splitlines()
in_table = False
for line in lines:
    if line.strip() == header:
        in_table = True
        continue
    if not in_table:
        continue
    if not line.strip().startswith('|'):
        break
    if line.strip().startswith('|---'):
        continue
    cells = [c.strip() for c in line.strip().strip('|').split('|')]
    if len(cells) < 5:
        continue
    fuente, estado, bloque = cells[2], cells[3].upper(), cells[4]
    blocked = 'bloquead' in bloque.lower()
    for hint, sids in legacy_hints.items():
        if hint in fuente:
            for sid in sids:
                legacy_rows[sid] = {'status': estado, 'blocked': blocked}
            break

with m.open_db(db_path) as conn:
    metrics = m.fetch_source_metrics(conn)

def old_sql_status(mx):
    runs_total = int(mx.get('runs_total') or 0)
    max_net = int(mx.get('max_loaded_network') or 0)
    max_any = int(mx.get('max_loaded_any') or 0)
    if runs_total == 0:
        return 'TODO'
    if max_net > 0:
        return 'DONE'
    if max_any > 0:
        return 'PARTIAL'
    return 'PARTIAL'

def mismatch_list(tracker_rows, use_new):
    out = []
    for sid in sorted(set(metrics) | set(tracker_rows)):
        checklist = (tracker_rows.get(sid) or {}).get('status', 'N/A')
        mx = metrics.get(sid) or {}
        if use_new:
            sql = m.sql_status_from_metrics(mx, tracker_blocked=bool((tracker_rows.get(sid) or {}).get('blocked')))
        else:
            sql = old_sql_status(mx)
        if checklist != 'N/A' and checklist != sql:
            out.append((sid, checklist, sql))
    return out

legacy_m = mismatch_list(legacy_rows, use_new=False)
new_m = mismatch_list(rows_new, use_new=True)

print('legacy_tracker_sources', len(legacy_rows))
print('new_tracker_sources', len(rows_new))
print('legacy_mismatches', len(legacy_m))
print('new_mismatches', len(new_m))
print('legacy_mismatch_rows', legacy_m)
print('new_mismatch_rows', new_m)
PY
```

Output:
```text
legacy_tracker_sources 28
new_tracker_sources 30
legacy_mismatches 1
new_mismatches 2
legacy_mismatch_rows [('parlamento_navarra_parlamentarios_forales', 'PARTIAL', 'DONE')]
new_mismatch_rows [('moncloa_referencias', 'TODO', 'PARTIAL'), ('moncloa_rss_referencias', 'TODO', 'PARTIAL')]
```

Interpretation:
- Navarra false mismatch removed by blocked-aware semantics.
- Moncloa now mapped (no longer invisible/N/A), so current tracker debt is surfaced as explicit mismatch until row is reconciled from `TODO`.

## Blocked behavior evidence (Navarra)

Command:
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md
```

Relevant output line:
```text
parlamento_navarra_parlamentarios_forales | PARTIAL | PARTIAL | 2/6 | 50 | 50 | 0 | 1/1 | OK
```

## Moncloa mapping evidence (dashboard + checker)

Command:
```bash
python3 - <<'PY'
from scripts import graph_ui_server as g
items = g.load_tracker_items(g.TRACKER_PATH)
row = next((it for it in items if it.get('tipo_dato') == 'Accion ejecutiva (Consejo de Ministros)'), None)
print('moncloa_source_ids', row.get('source_ids') if row else None)
PY
```

Output:
```text
moncloa_source_ids ['moncloa_referencias', 'moncloa_rss_referencias']
```

Checker lines:
```text
moncloa_referencias     | TODO | PARTIAL | ... | MISMATCH
moncloa_rss_referencias | TODO | PARTIAL | ... | MISMATCH
```

## Escalation rule check (DONE regression risk)

Command:
```bash
python3 - <<'PY'
from pathlib import Path
from scripts import e2e_tracker_status as m

tracker_path = Path('docs/etl/e2e-scrape-load-tracker.md')
rows = m.parse_tracker_rows(tracker_path)
with m.open_db(Path('etl/data/staging/politicos-es.db')) as conn:
    metrics = m.fetch_source_metrics(conn)

def old_sql_status(mx):
    runs_total = int(mx.get('runs_total') or 0)
    max_net = int(mx.get('max_loaded_network') or 0)
    max_any = int(mx.get('max_loaded_any') or 0)
    if runs_total == 0:
        return 'TODO'
    if max_net > 0:
        return 'DONE'
    if max_any > 0:
        return 'PARTIAL'
    return 'PARTIAL'

regress = []
for sid, meta in rows.items():
    if meta.get('status') != 'DONE':
        continue
    mx = metrics.get(sid) or {}
    old = old_sql_status(mx)
    new = m.sql_status_from_metrics(mx, tracker_blocked=bool(meta.get('blocked')))
    if old == 'DONE' and new != 'DONE':
        regress.append((sid, old, new))

print('done_regression_count', len(regress))
print('done_regression_rows', regress)
PY
```

Output:
```text
done_regression_count 0
done_regression_rows []
```

Result:
- No `DONE` source regressed under the blocked-aware rule.
- No escalation required.

