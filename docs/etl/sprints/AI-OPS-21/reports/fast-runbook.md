# AI-OPS-21 FAST Runbook (Evidence Packet)

Goal:
- Generate the full evidence packet to adjudicate gates G1..G6 with minimal ambiguity.

Repo:
- `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Step 0: folders
```bash
mkdir -p docs/etl/sprints/AI-OPS-21/evidence docs/etl/sprints/AI-OPS-21/reports docs/etl/sprints/AI-OPS-21/exports
```

## Step 1: GH Pages build (exports + strict validation)
```bash
just explorer-gh-pages-build > docs/etl/sprints/AI-OPS-21/evidence/gh-pages-build.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-21/evidence/gh-pages-build.exit
```

## Step 2: Validate citizen artifacts + budget summary
```bash
for f in docs/gh-pages/citizen/data/citizen*.json; do
  echo "VALIDATE $f"
  python3 scripts/validate_citizen_snapshot.py --path "$f" --max-bytes 5000000 --strict-grid
done > docs/etl/sprints/AI-OPS-21/evidence/citizen-validate-post.log 2>&1
```

```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-21/evidence/citizen-json-budget.txt
import json
from pathlib import Path

def one(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding='utf-8'))
    meta = obj.get('meta') or {}
    return {
      'file': path.name,
      'bytes': path.stat().st_size,
      'as_of_date': meta.get('as_of_date'),
      'computed_method': meta.get('computed_method'),
      'topics': len(obj.get('topics') or []),
      'parties': len(obj.get('parties') or []),
      'ptp': len(obj.get('party_topic_positions') or []),
      'programas_rows': len(obj.get('party_concern_programas') or []),
    }

out=[]
for p in sorted(Path('docs/gh-pages/citizen/data').glob('citizen*.json')):
    out.append(one(p))

for r in out:
    ok = (r['bytes'] or 0) <= 5_000_000
    print(f"{r['file']}: bytes={r['bytes']} ok={str(ok).lower()} as_of_date={r['as_of_date']} computed_method={r['computed_method']} topics={r['topics']} parties={r['parties']} ptp={r['ptp']} programas_rows={r['programas_rows']}")
PY
```

## Step 3: Baseline coverage + coherence evidence
See:
- `docs/etl/sprints/AI-OPS-21/reports/query-pack-baseline.md`

Outputs:
- `docs/etl/sprints/AI-OPS-21/evidence/baseline_coverage.json`
- `docs/etl/sprints/AI-OPS-21/evidence/baseline_coherence.json`

## Step 4: Link-check
```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-21/evidence/link-check.json
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

## Step 5: Perf budget
```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-21/evidence/perf-budget.txt
from pathlib import Path

paths = [
    Path('docs/gh-pages/citizen/data/citizen.json'),
    Path('docs/gh-pages/citizen/data/citizen_votes.json'),
    Path('docs/gh-pages/citizen/data/citizen_declared.json'),
]

sizes = [(p.name, p.stat().st_size) for p in paths]
combined = dict(sizes).get('citizen.json', 0)
votes = dict(sizes).get('citizen_votes.json', 0)
declared = dict(sizes).get('citizen_declared.json', 0)

print('# AI-OPS-21 perf budget (static downloads)')
for name, n in sizes:
    print(f'{name}: bytes={n}')
print('---')
print(f'votes+declared total bytes={votes + declared}')
print(f'combined+votes+declared total bytes={combined + votes + declared}')
print('---')
print('Coherence view policy: lazy-load votes+declared (+combined if base method is not combined).')
print('Target: <= ~3MB total JSON download for coherence view entry path.')
PY
```

## Step 6: Strict gate + parity evidence
```bash
just etl-tracker-gate > docs/etl/sprints/AI-OPS-21/evidence/tracker-gate-postrun.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-21/evidence/tracker-gate-postrun.exit

python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/etl/sprints/AI-OPS-21/evidence/status-postrun.json
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
```

```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-21/evidence/status-parity-postrun.txt
import json
from pathlib import Path

final = json.loads(Path('docs/etl/sprints/AI-OPS-21/evidence/status-postrun.json').read_text(encoding='utf-8'))
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
print('# AI-OPS-21 status parity summary')
for name, path in checks:
    fv = pick(final, path)
    pv = pick(published, path)
    match = fv == pv
    overall_match = overall_match and match
    print(f'{name}: final={fv} published={pv} match={str(match).lower()}')
print(f'overall_match={str(overall_match).lower()}')
PY
```

## Step 7: Tests
```bash
just etl-test > docs/etl/sprints/AI-OPS-21/evidence/tests.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-21/evidence/tests.exit
```

