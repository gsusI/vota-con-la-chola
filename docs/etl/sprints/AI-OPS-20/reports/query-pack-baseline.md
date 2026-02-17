# AI-OPS-20 Baseline + Command Pack (Citizen Dashboard v3)

Goal:
- Provide deterministic commands to capture baseline + postrun evidence for AI-OPS-20.

Repo context:
- `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

Defaults:
- `DB_PATH=etl/data/staging/politicos-es.db`
- `GH_PAGES_DIR=docs/gh-pages`

## 1) Baseline: citizen.json validation (current)

```bash
mkdir -p docs/etl/sprints/AI-OPS-20/evidence

python3 scripts/validate_citizen_snapshot.py \
  --path docs/gh-pages/citizen/data/citizen.json \
  --max-bytes 5000000 \
  --strict-grid \
  > docs/etl/sprints/AI-OPS-20/evidence/baseline_citizen_validate.json
```

Sanity peek:
```bash
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('docs/etl/sprints/AI-OPS-20/evidence/baseline_citizen_validate.json').read_text(encoding='utf-8'))
print('bytes', obj.get('bytes'))
print('topics', obj.get('topics'))
print('parties', obj.get('parties'))
print('ptp', obj.get('party_topic_positions'))
print('as_of_date', obj.get('as_of_date'))
print('computed_method', obj.get('computed_method'))
print('stances', obj.get('stances'))
print('programas_stances', obj.get('programas_stances'))
PY
```

## 2) Baseline: methods_available

```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-20/evidence/baseline_methods_available.json
import json
from pathlib import Path
data=json.loads(Path('docs/gh-pages/citizen/data/citizen.json').read_text(encoding='utf-8'))
print(json.dumps({'methods_available': (data.get('meta') or {}).get('methods_available')}, ensure_ascii=True, separators=(',',':')))
PY
```

## 3) Baseline: strict tracker gate (must remain green)

```bash
just etl-tracker-gate > docs/etl/sprints/AI-OPS-20/evidence/baseline_tracker_gate.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-20/evidence/baseline_tracker_gate.exit
```

## 4) Status export + parity template (overall_match)

Export status snapshot to sprint evidence and to GH Pages, then check `overall_match=true` for required keys.

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-20/evidence/status-baseline.json

python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json

python3 - <<'PY' > docs/etl/sprints/AI-OPS-20/evidence/status-parity-baseline.txt
import json
from pathlib import Path

final = json.loads(Path('docs/etl/sprints/AI-OPS-20/evidence/status-baseline.json').read_text(encoding='utf-8'))
published = json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))

checks = [
  ('summary.tracker.mismatch', (('summary','tracker','mismatch'))),
  ('summary.tracker.waived_mismatch', (('summary','tracker','waived_mismatch'))),
  ('summary.tracker.done_zero_real', (('summary','tracker','done_zero_real'))),
  ('summary.tracker.waivers_expired', (('summary','tracker','waivers_expired'))),
  ('analytics.impact.indicator_series_total', (('analytics','impact','indicator_series_total'))),
  ('analytics.impact.indicator_points_total', (('analytics','impact','indicator_points_total'))),
]

def pick(obj, path):
    cur = obj
    for k in path:
        cur = (cur or {}).get(k)
    return cur

overall_match = True
print('# AI-OPS-20 status parity baseline')
for name, path in checks:
    fv = pick(final, path)
    pv = pick(published, path)
    match = fv == pv
    overall_match = overall_match and match
    print(f'{name}: final={fv} published={pv} match={str(match).lower()}')
print(f'overall_match={str(overall_match).lower()}')
PY
```

## 5) Postrun template: GH Pages build evidence

```bash
just explorer-gh-pages-build > docs/etl/sprints/AI-OPS-20/evidence/gh-pages-build.log 2>&1
```

## 6) Postrun template: tests

```bash
just etl-test > docs/etl/sprints/AI-OPS-20/evidence/tests.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-20/evidence/tests.exit
```

