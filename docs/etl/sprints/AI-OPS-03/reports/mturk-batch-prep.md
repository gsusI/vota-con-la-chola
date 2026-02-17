# MTurk batch prep report: ai-ops-03 (congreso_intervenciones)

- Timestamp UTC: 2026-02-16T10:15:29Z
- DB: `etl/data/staging/politicos-es.db`
- Target source: `congreso_intervenciones`
- Target size: `120` rows (`6x20`)
- Batch prefix: `congreso-b`

## 1) Queue and source diagnostics

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT status, COUNT(*) AS c FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones' GROUP BY status ORDER BY status;"
```

```text
ignored|474
resolved|50
```

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT review_reason, COUNT(*) AS c FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones' GROUP BY review_reason ORDER BY c DESC;"
```

```text
no_signal|474
low_confidence|46
conflicting_signal|4
```

- `pending` is currently `0` (no pending rows).
- Prepared batches are therefore drawn from high-stakes no-MTurk-adjudicated hotspots to provide a focused 2nd-pass target set:
  - `status = 'ignored'`
  - `review_reason IN ('low_confidence','conflicting_signal','no_signal')`
  - `note NOT LIKE 'mturk batch %'`
  - ordered by high-stakes first, then reason priority (`conflicting_signal` > `low_confidence` > `no_signal`), then stakes rank, then confidence.

## 2) Candidate pool characteristics

```bash
sqlite3 etl/data/staging/politicos-es.db "WITH candidate AS (SELECT r.evidence_id, COALESCE(ts.is_high_stakes,0) AS is_high_stakes, r.review_reason FROM topic_evidence_reviews r JOIN topic_evidence e ON e.evidence_id=r.evidence_id LEFT JOIN topic_set_topics ts ON ts.topic_set_id=e.topic_set_id AND ts.topic_id=e.topic_id WHERE r.source_id='congreso_intervenciones' AND r.status='ignored' AND r.review_reason IN ('low_confidence','conflicting_signal','no_signal') AND (r.note IS NOT NULL AND r.note NOT LIKE 'mturk batch %') ) SELECT is_high_stakes, COUNT(*) AS c FROM candidate GROUP BY is_high_stakes;"
```

```text
0|111
1|309
```

```bash
sqlite3 etl/data/staging/politicos-es.db "WITH candidate AS (SELECT r.evidence_id, COALESCE(ts.is_high_stakes,0) AS is_high_stakes, r.review_reason FROM topic_evidence_reviews r JOIN topic_evidence e ON e.evidence_id=r.evidence_id LEFT JOIN topic_set_topics ts ON ts.topic_set_id=e.topic_set_id AND ts.topic_id=e.topic_id WHERE r.source_id='congreso_intervenciones' AND r.status='ignored' AND r.review_reason IN ('low_confidence','conflicting_signal','no_signal') AND (r.note IS NOT NULL AND r.note NOT LIKE 'mturk batch %') ) SELECT review_reason, COUNT(*) AS c FROM candidate WHERE is_high_stakes=1 GROUP BY review_reason ORDER BY c DESC;"
```

```text
no_signal|309
```

```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "WITH ordered AS (SELECT t.label AS topic_label, r.review_reason FROM topic_evidence_reviews r JOIN topic_evidence e ON e.evidence_id = r.evidence_id LEFT JOIN topics t ON t.topic_id = e.topic_id LEFT JOIN topic_set_topics ts ON ts.topic_set_id = e.topic_set_id AND ts.topic_id = e.topic_id WHERE r.source_id='congreso_intervenciones' AND r.status='ignored' AND r.review_reason IN ('low_confidence','conflicting_signal','no_signal') AND (r.note IS NOT NULL AND r.note NOT LIKE 'mturk batch %') ORDER BY COALESCE(ts.is_high_stakes, 0) DESC, CASE r.review_reason WHEN 'conflicting_signal' THEN 1 WHEN 'low_confidence' THEN 2 ELSE 3 END, COALESCE(ts.stakes_rank,9999) ASC, e.confidence ASC, r.updated_at DESC, r.evidence_id DESC LIMIT 120 ) SELECT topic_label, COUNT(*) AS c FROM ordered GROUP BY topic_label ORDER BY c DESC LIMIT 10;"
```

Top topics in selected set:

```text
topic_label,c
"Proyecto de Ley Orgánica de medidas en materia de eficiencia del Servicio Público de Justicia.",30
"Proyecto de Ley de Movilidad Sostenible.",27
"Proyecto de Ley Orgánica de representación paritaria y presencia equilibrada de mujeres y hombres.",20
"Proyecto de Ley de prevención de las pérdidas y el desperdicio alimentario.",17
"Proyecto de Ley por la que se regulan los servicios de atención a la clientela.",14
"Proyecto de Ley por la que se regulan las enseñanzas artísticas superiores y se establece la organización y equivalencias de las enseñanzas artísticas profesionales.",12
```

## 3) Prepared batch folders and files

Created:
- `etl/data/raw/manual/mturk_reviews/mturk-20260216-congreso-b01`
- `etl/data/raw/manual/mturk_reviews/mturk-20260216-congreso-b02`
- `etl/data/raw/manual/mturk_reviews/mturk-20260216-congreso-b03`
- `etl/data/raw/manual/mturk_reviews/mturk-20260216-congreso-b04`
- `etl/data/raw/manual/mturk_reviews/mturk-20260216-congreso-b05`
- `etl/data/raw/manual/mturk_reviews/mturk-20260216-congreso-b06`

Each folder contains:
- `tasks_input.csv` (20 rows each)
- `workers_raw.csv` (header-only template)
- `decisions_adjudicated.csv` (header-only template)

`tasks_input.csv` schema (exact headers):
- `batch_id,evidence_id,person_name,topic_label,evidence_excerpt,evidence_date,source_url,review_reason`

## 4) Validation evidence

```bash
python3 - <<'PY'
import csv
from pathlib import Path

base = Path('etl/data/raw/manual/mturk_reviews')
batches = [
    'mturk-20260216-congreso-b01',
    'mturk-20260216-congreso-b02',
    'mturk-20260216-congreso-b03',
    'mturk-20260216-congreso-b04',
    'mturk-20260216-congreso-b05',
    'mturk-20260216-congreso-b06',
]

expected_headers = {
    'tasks_input.csv': [
        'batch_id', 'evidence_id', 'person_name', 'topic_label', 'evidence_excerpt', 'evidence_date', 'source_url', 'review_reason'
    ],
    'workers_raw.csv': ['batch_id', 'evidence_id', 'worker_id', 'worker_stance', 'worker_confidence', 'worker_note'],
    'decisions_adjudicated.csv': ['batch_id', 'evidence_id', 'proposed_status', 'proposed_final_stance', 'agreement_ratio', 'adjudicator_note'],
}

seen = set()
rows_total = 0
for b in batches:
    bdir = base / b
    for fn, exp in expected_headers.items():
        path = bdir / fn
        if not path.exists():
            raise SystemExit(f'missing file: {path}')
        with path.open(newline='') as f:
            header = next(csv.reader(f), [])
            if header != exp:
                raise SystemExit(f'bad header in {path}: {header} != {exp}')

    with (bdir / 'tasks_input.csv').open(newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            iid = row['evidence_id'].strip()
            if not iid:
                raise SystemExit(f'empty evidence_id in {bdir / "tasks_input.csv"}')
            if iid in seen:
                raise SystemExit(f'duplicate evidence_id across batches: {iid}')
            seen.add(iid)
            rows_total += 1

print(f'rows_total={rows_total}')
print(f'unique_evidence_ids={len(seen)}')
print(f'duplicate_count={rows_total-len(seen)}')
PY
```

Observed:
- `rows_total=120`
- `unique_evidence_ids=120`
- `duplicate_count=0`

## 5) Reproduction command

```bash
DB=etl/data/staging/politicos-es.db
DATE=20260216
BASE=etl/data/raw/manual/mturk_reviews
BATCH_PREFIX=congreso-b
BATCH_SIZE=20
BATCHS=6

query_template="SELECT
  '__BATCH_ID__' AS batch_id,
  r.evidence_id,
  COALESCE(p.full_name, '') AS person_name,
  COALESCE(t.label, '') AS topic_label,
  COALESCE(e.excerpt, '') AS evidence_excerpt,
  COALESCE(e.evidence_date, '') AS evidence_date,
  COALESCE(e.source_url, '') AS source_url,
  r.review_reason
FROM topic_evidence_reviews r
JOIN topic_evidence e ON e.evidence_id = r.evidence_id
LEFT JOIN persons p ON p.person_id = e.person_id
LEFT JOIN topics t ON t.topic_id = e.topic_id
LEFT JOIN topic_set_topics ts
  ON ts.topic_set_id = e.topic_set_id
 AND ts.topic_id = e.topic_id
WHERE r.source_id = 'congreso_intervenciones'
  AND r.status = 'ignored'
  AND r.review_reason IN ('low_confidence','conflicting_signal','no_signal')
  AND (r.note IS NOT NULL AND r.note NOT LIKE 'mturk batch %')
ORDER BY
  COALESCE(ts.is_high_stakes, 0) DESC,
  CASE r.review_reason
    WHEN 'conflicting_signal' THEN 1
    WHEN 'low_confidence' THEN 2
    ELSE 3
  END,
  COALESCE(ts.stakes_rank, 9999) ASC,
  e.confidence ASC,
  r.updated_at DESC,
  r.evidence_id DESC
"

for i in $(seq 0 $((BATCHS-1))); do
  idx=$(printf '%02d' $((i+1)))
  batch_id="mturk-${DATE}-${BATCH_PREFIX}${idx}"
  batch_dir="${BASE}/${batch_id}"
  mkdir -p "$batch_dir"
  offset=$((i * BATCH_SIZE))

  query="${query_template//__BATCH_ID__/$batch_id} LIMIT ${BATCH_SIZE} OFFSET ${offset}"
  sqlite3 -header -csv "$DB" "$query;" > "$batch_dir/tasks_input.csv"
  echo 'batch_id,evidence_id,worker_id,worker_stance,worker_confidence,worker_note' > "$batch_dir/workers_raw.csv"
  echo 'batch_id,evidence_id,proposed_status,proposed_final_stance,agreement_ratio,adjudicator_note' > "$batch_dir/decisions_adjudicated.csv"
done
```

## Acceptance check
- schema valid (all required files + required headers): PASS
- duplicate evidence_id in new batches: PASS (`0`)
