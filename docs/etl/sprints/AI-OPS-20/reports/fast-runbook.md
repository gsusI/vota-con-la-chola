# AI-OPS-20 FAST Runbook (L1 throughput)

Goal:
- Generate the full evidence packet to adjudicate gates G1..G6 with minimal ambiguity.

Repo:
- `REPO_ROOT/vota-con-la-chola`

## Step 0: folders
```bash
mkdir -p docs/etl/sprints/AI-OPS-20/evidence docs/etl/sprints/AI-OPS-20/reports docs/etl/sprints/AI-OPS-20/exports
```

## Step 1: export + validate citizen artifacts (postrun)

If the build exports multiple citizen JSONs, validate each:
```bash
for f in docs/gh-pages/citizen/data/citizen*.json; do
  echo "VALIDATE $f"
  python3 scripts/validate_citizen_snapshot.py --path "$f" --max-bytes 5000000 --strict-grid
done > docs/etl/sprints/AI-OPS-20/evidence/citizen-validate-post.log 2>&1
```

Record budget summary:
```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-20/evidence/citizen-json-budget.txt
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
    print(f\"{r['file']}: bytes={r['bytes']} ok={str(ok).lower()} as_of_date={r['as_of_date']} computed_method={r['computed_method']} topics={r['topics']} parties={r['parties']} ptp={r['ptp']} programas_rows={r['programas_rows']}\")
PY
```

## Step 2: GH Pages build (must be reproducible)
```bash
just explorer-gh-pages-build > docs/etl/sprints/AI-OPS-20/evidence/gh-pages-build.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-20/evidence/gh-pages-build.exit
```

## Step 3: Link-check (audit targets)
- Create `docs/etl/sprints/AI-OPS-20/reports/link-check.md` with:
  - required_links list (citizen + explorers)
  - broken_targets count
  - Verdict PASS/FAIL

## Step 4: Walkthrough + URL matrix + honesty audit
- Walkthrough: `docs/etl/sprints/AI-OPS-20/reports/citizen-walkthrough.md`
- URL matrix: `docs/etl/sprints/AI-OPS-20/reports/shareable-url-matrix.md`
- Honesty audit: `docs/etl/sprints/AI-OPS-20/reports/honesty-audit.md`
- Mobile/a11y smoke: `docs/etl/sprints/AI-OPS-20/reports/citizen-mobile-a11y-smoke.md`

## Step 5: Strict gate + parity evidence
```bash
just etl-tracker-gate > docs/etl/sprints/AI-OPS-20/evidence/tracker-gate-postrun.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-20/evidence/tracker-gate-postrun.exit

python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-20/evidence/status-postrun.json

python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json

python3 - <<'PY' > docs/etl/sprints/AI-OPS-20/evidence/status-parity-postrun.txt
import json
from pathlib import Path

final = json.loads(Path('docs/etl/sprints/AI-OPS-20/evidence/status-postrun.json').read_text(encoding='utf-8'))
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
print('# AI-OPS-20 status parity summary')
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
```bash
just etl-test > docs/etl/sprints/AI-OPS-20/evidence/tests.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-20/evidence/tests.exit
```

