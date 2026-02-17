# AI-OPS-22 FAST Runbook (Evidence + Gates)

Date: 2026-02-17  
Owner: L2 Specialist Builder

Goal: generate deterministic evidence artifacts for gate adjudication after alignment UI changes.

## Step 1: Baseline Metrics + Prefs Sample
Run the query pack:
- `docs/etl/sprints/AI-OPS-22/reports/query-pack-baseline.md`

Expected outputs:
- `docs/etl/sprints/AI-OPS-22/evidence/baseline_metrics.json`
- `docs/etl/sprints/AI-OPS-22/exports/prefs_sample_v1.json`

## Step 2: Build GH Pages Output
```bash
just explorer-gh-pages-build > docs/etl/sprints/AI-OPS-22/evidence/gh-pages-build.log 2>&1
echo $? > docs/etl/sprints/AI-OPS-22/evidence/gh-pages-build.exit
```

## Step 3: Validate Citizen Artifacts + Budget
```bash
python3 scripts/validate_citizen_snapshot.py --in docs/gh-pages/citizen/data/citizen.json > docs/etl/sprints/AI-OPS-22/evidence/citizen-validate-post.log 2>&1
python3 scripts/validate_citizen_snapshot.py --in docs/gh-pages/citizen/data/citizen_votes.json >> docs/etl/sprints/AI-OPS-22/evidence/citizen-validate-post.log 2>&1
python3 scripts/validate_citizen_snapshot.py --in docs/gh-pages/citizen/data/citizen_declared.json >> docs/etl/sprints/AI-OPS-22/evidence/citizen-validate-post.log 2>&1

python3 - <<'PY'
import os
paths=[
  'docs/gh-pages/citizen/data/citizen.json',
  'docs/gh-pages/citizen/data/citizen_votes.json',
  'docs/gh-pages/citizen/data/citizen_declared.json',
]
total=0
for p in paths:
  sz=os.path.getsize(p)
  total += sz
  print(f\"{p}\\t{sz}\")
print(f\"TOTAL\\t{total}\")
PY > docs/etl/sprints/AI-OPS-22/evidence/perf-budget.txt
```

## Step 4: Link Check (Auditability)
Pragmatic inline link-check (same method as AI-OPS-20/21):
```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-22/evidence/link-check.json
import json
from pathlib import Path

ROOT = Path('docs/gh-pages')
DATA_DIR = Path('docs/gh-pages/citizen/data')
paths = sorted(DATA_DIR.glob('citizen*.json'))

def norm_path(u: str) -> str:
    if u.startswith('../'):
        u2 = u[3:]
    elif u.startswith('./'):
        u2 = u[2:]
    else:
        u2 = u
    u2 = u2.split('?', 1)[0]
    u2 = u2.split('#', 1)[0]
    return u2

def check_one(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding='utf-8'))

    links = []
    missing_required = 0
    non_relative = 0

    def add(u, where, required=True):
        nonlocal missing_required, non_relative
        if not u:
            if required:
                missing_required += 1
            return
        u = str(u)
        if u.startswith('http://') or u.startswith('https://'):
            non_relative += 1
        links.append({'url': u, 'where': where})

    for t in obj.get('topics') or []:
        l = (t.get('links') or {})
        add(l.get('explorer_temas'), 'topics.links.explorer_temas', True)
        add(l.get('explorer_positions'), 'topics.links.explorer_positions', True)
        add(l.get('explorer_evidence'), 'topics.links.explorer_evidence', True)

    for p in obj.get('parties') or []:
        l = (p.get('links') or {})
        add(l.get('explorer_politico_party'), 'parties.links.explorer_politico_party', True)

    for r in obj.get('party_topic_positions') or []:
        l = (r.get('links') or {})
        add(l.get('explorer_temas'), 'party_topic_positions.links.explorer_temas', True)
        add(l.get('explorer_positions'), 'party_topic_positions.links.explorer_positions', True)

    missing_targets = []
    unique_targets = {}

    for x in links:
        u = x['url']
        pth = norm_path(u)
        if not pth:
            continue
        if pth.endswith('/'):
            target = ROOT / pth / 'index.html'
        else:
            target = ROOT / pth
        unique_targets[str(target)] = unique_targets.get(str(target), 0) + 1
        if not target.exists():
            missing_targets.append({'target': str(target), 'url': u, 'where': x['where']})

    return {
        'file': str(path),
        'links_total': len(links),
        'missing_required_links_total': missing_required,
        'non_relative_total': non_relative,
        'unique_targets_total': len(unique_targets),
        'missing_targets_total': len({m['target'] for m in missing_targets}),
        'missing_examples': missing_targets[:25],
    }

results = [check_one(p) for p in paths]
out = {
    'datasets_checked': [str(p) for p in paths],
    'results': results,
    'summary': {
        'datasets': len(results),
        'missing_required_links_total': sum(r['missing_required_links_total'] for r in results),
        'non_relative_total': sum(r['non_relative_total'] for r in results),
        'missing_targets_total': sum(r['missing_targets_total'] for r in results),
    }
}
print(json.dumps(out, indent=2, ensure_ascii=True))
PY
```

## Step 5: Strict Gate + Status Parity
```bash
just etl-tracker-gate > docs/etl/sprints/AI-OPS-22/evidence/tracker-gate-postrun.log 2>&1
echo $? > docs/etl/sprints/AI-OPS-22/evidence/tracker-gate-postrun.exit

python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/etl/sprints/AI-OPS-22/evidence/status-postrun.json
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
```

```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-22/evidence/status-parity-postrun.txt
import json
from pathlib import Path

final = json.loads(Path('docs/etl/sprints/AI-OPS-22/evidence/status-postrun.json').read_text(encoding='utf-8'))
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
print('# AI-OPS-22 status parity summary')
for name, path in checks:
    fv = pick(final, path)
    pv = pick(published, path)
    match = fv == pv
    overall_match = overall_match and match
    print(f'{name}: final={fv} published={pv} match={str(match).lower()}')
print(f'overall_match={str(overall_match).lower()}')
PY
```

## Step 6: Tests
Use the existing test entrypoint:
```bash
just etl-test > docs/etl/sprints/AI-OPS-22/evidence/tests.log 2>&1
echo $? > docs/etl/sprints/AI-OPS-22/evidence/tests.exit
```

## Step 7: Walkthrough + Privacy Audit
- Walkthrough: `docs/etl/sprints/AI-OPS-22/reports/citizen-alignment-walkthrough.md`
- Privacy audit: `docs/etl/sprints/AI-OPS-22/reports/privacy-audit.md`
- URL matrix: `docs/etl/sprints/AI-OPS-22/exports/url-matrix.csv`

## Acceptance Quick Checks
```bash
test \"$(cat docs/etl/sprints/AI-OPS-22/evidence/gh-pages-build.exit)\" = \"0\"
test \"$(cat docs/etl/sprints/AI-OPS-22/evidence/tracker-gate-postrun.exit)\" = \"0\"
test \"$(cat docs/etl/sprints/AI-OPS-22/evidence/tests.exit)\" = \"0\"
```
