# AI-OPS-17 Query Pack (Baseline + Gates)

Date: 2026-02-17  
Sprint: `AI-OPS-17`

Goal: provide a runnable baseline/postrun KPI + gate command pack for the citizen GH Pages app iteration.

Assumptions:
- DB: `etl/data/staging/politicos-es.db`
- GH pages build dir: `docs/gh-pages`
- Citizen artifact path: `docs/gh-pages/citizen/data/citizen.json`

## 0) Preflight (paths + folders)

```bash
mkdir -p docs/etl/sprints/AI-OPS-17/evidence docs/etl/sprints/AI-OPS-17/exports
test -f etl/data/staging/politicos-es.db
```

If `docs/gh-pages/citizen/data/citizen.json` does not exist yet:

```bash
just explorer-gh-pages-build
```

## 1) Citizen Snapshot Validator (baseline)

Writes a compact JSON KPI summary (machine-parseable) from `validate_citizen_snapshot.py`:

```bash
python3 scripts/validate_citizen_snapshot.py \
  --path docs/gh-pages/citizen/data/citizen.json \
  --max-bytes 5000000 \
  --strict-grid \
  > docs/etl/sprints/AI-OPS-17/evidence/baseline_citizen_validate.json
```

## 2) Topic Positions Method Coverage (baseline)

Capture availability and distribution of `computed_method` for the citizen scope (`topic_set_id=1`, `institution_id=7`):

```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "
SELECT
  computed_method,
  COUNT(DISTINCT as_of_date) AS as_of_dates,
  COUNT(DISTINCT computed_version) AS versions,
  MAX(as_of_date) AS max_as_of_date,
  COUNT(*) AS positions_total
FROM topic_positions
WHERE topic_set_id=1
  AND institution_id=7
GROUP BY computed_method
ORDER BY positions_total DESC, computed_method ASC;
" > docs/etl/sprints/AI-OPS-17/evidence/baseline_topic_positions_methods.csv
```

## 3) Programas Lane Coverage (baseline)

### 3.1 Extract programas meta from the citizen artifact

This aligns “programas coverage” with what the citizen UI will actually display:

```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-17/evidence/baseline_programas_meta.json
import json
from pathlib import Path

p = Path("docs/gh-pages/citizen/data/citizen.json")
d = json.loads(p.read_text(encoding="utf-8"))
meta = (d.get("meta") or {}).get("programas")
print(json.dumps(meta, ensure_ascii=True, separators=(",", ":")))
PY
```

### 3.2 (Optional) Raw programas_partidos metrics from SQLite

```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "
SELECT 'programas_source_records_total' AS metric, COUNT(*) AS value
FROM source_records
WHERE source_id='programas_partidos'
UNION ALL
SELECT 'programas_text_documents_total', COUNT(*)
FROM text_documents
WHERE source_id='programas_partidos'
UNION ALL
SELECT 'programas_topic_evidence_total', COUNT(*)
FROM topic_evidence
WHERE source_id='programas_partidos' AND evidence_type='declared:programa'
UNION ALL
SELECT 'programas_declared_with_signal', COUNT(*)
FROM topic_evidence
WHERE source_id='programas_partidos'
  AND evidence_type='declared:programa'
  AND stance IN ('support','oppose','mixed')
UNION ALL
SELECT 'programas_review_pending', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='programas_partidos'
  AND lower(status)='pending'
" > docs/etl/sprints/AI-OPS-17/exports/programas_metrics.csv
```

## 4) Strict Tracker Gate (must stay green)

Preferred (Docker, canonical):

```bash
set +e
just etl-tracker-gate
echo $? > docs/etl/sprints/AI-OPS-17/evidence/tracker-gate-postrun.exit
set -e
```

Optional (host Python, if you are not using Docker):

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17 \
  --fail-on-mismatch \
  --fail-on-done-zero-real
```

## 5) Status Export + Parity (overall_match)

Export status snapshot to sprint evidence and to GH Pages, then check `overall_match=true` for required keys.

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-17/evidence/status-postrun.json

python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json

python3 - <<'PY' > docs/etl/sprints/AI-OPS-17/evidence/status-parity-postrun.txt
import json
from pathlib import Path

final = json.loads(Path('docs/etl/sprints/AI-OPS-17/evidence/status-postrun.json').read_text(encoding='utf-8'))
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
print('# AI-OPS-17 status parity summary')
for name, path in checks:
    fv = pick(final, path)
    pv = pick(published, path)
    match = fv == pv
    overall_match = overall_match and match
    print(f'{name}: final={fv} published={pv} match={str(match).lower()}')
print(f'overall_match={str(overall_match).lower()}')
PY
```

