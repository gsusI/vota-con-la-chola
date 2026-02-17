# AI-OPS-19 Query Pack (Baseline + Gates)

Date: 2026-02-17  
Sprint: `AI-OPS-19`

Goal: provide a runnable baseline/postrun KPI + gate command pack for the `programas_partidos` lane.

## 1) Baseline KPI Packet (programas_partidos)

Writes a compact CSV of counts (baseline or postrun, depending on current DB state):

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
WHERE source_id='programas_partidos'
UNION ALL
SELECT 'programas_topic_evidence_with_topic', COUNT(*)
FROM topic_evidence
WHERE source_id='programas_partidos' AND topic_id IS NOT NULL
UNION ALL
SELECT 'programas_declared_with_signal', COUNT(*)
FROM topic_evidence
WHERE source_id='programas_partidos'
  AND stance IN ('support','oppose','mixed')
UNION ALL
SELECT 'programas_declared_no_signal', COUNT(*)
FROM topic_evidence
WHERE source_id='programas_partidos'
  AND stance='no_signal'
UNION ALL
SELECT 'programas_review_pending', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='programas_partidos'
  AND lower(status)='pending'
" > docs/etl/sprints/AI-OPS-19/exports/programas_metrics.csv
```

## 2) Strict Gate (Must Stay Green)

```bash
just etl-tracker-gate
```

## 3) Status Export + Parity (overall_match)

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-19/evidence/status-postrun.json

python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json

python3 - <<'PY' > docs/etl/sprints/AI-OPS-19/evidence/status-parity-postrun.txt
import json
from pathlib import Path

final = json.loads(Path('docs/etl/sprints/AI-OPS-19/evidence/status-postrun.json').read_text(encoding='utf-8'))
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
print('# AI-OPS-19 status parity summary')
for name, path in checks:
    fv = pick(final, path)
    pv = pick(published, path)
    match = fv == pv
    overall_match = overall_match and match
    print(f'{name}: final={fv} published={pv} match={str(match).lower()}')
print(f'overall_match={str(overall_match).lower()}')
PY
```

## 4) Suggested Pass Thresholds (Decision Support)
- `programas_declared_with_signal > 0` is the minimum “signal floor”.
- Keep `programas_review_pending / NULLIF(programas_topic_evidence_total, 0)` bounded (target `<= 0.35`) to avoid review debt explosions.
