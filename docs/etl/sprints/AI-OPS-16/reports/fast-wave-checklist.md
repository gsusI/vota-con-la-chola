# AI-OPS-16 FAST Wave Checklist (Tasks 8-20)

Date:
- `2026-02-17`

Purpose:
- Deterministic operator checklist for FAST wave execution.
- Executes Tasks `8` through `20` in locked dependency order.
- Preserves strict gate/parity hard constraints and explicit `no-op` handling.

## Runtime constants

```bash
export DB_PATH="etl/data/staging/politicos-es.db"
export SOURCE_ID="congreso_intervenciones"
export TRACKER_PATH="docs/etl/e2e-scrape-load-tracker.md"
export WAIVERS_PATH="docs/etl/mismatch-waivers.json"
export GATE_AS_OF="2026-02-17"
export POS_AS_OF="2026-02-16"

mkdir -p docs/etl/sprints/AI-OPS-16/evidence docs/etl/sprints/AI-OPS-16/exports docs/etl/sprints/AI-OPS-16/reports
```

## Task 8 (P8 FAST) - Baseline capture

Run:

```bash
sqlite3 -header -csv "$DB_PATH" "
SELECT 'declared_total' AS metric, COUNT(*) AS value
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'declared_with_signal',
       SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'declared_with_signal_pct',
       ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 6)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID';
" > docs/etl/sprints/AI-OPS-16/exports/declared_kpi_baseline.csv

{
  echo "# AI-OPS-16 declared baseline"
  date -u +"captured_at_utc=%Y-%m-%dT%H:%M:%SZ"
  cat docs/etl/sprints/AI-OPS-16/exports/declared_kpi_baseline.csv
  python3 scripts/e2e_tracker_status.py \
    --db "$DB_PATH" \
    --tracker "$TRACKER_PATH" \
    --waivers "$WAIVERS_PATH" \
    --as-of-date "$GATE_AS_OF"
} > docs/etl/sprints/AI-OPS-16/evidence/declared-baseline.log
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/declared-baseline.log
test -f docs/etl/sprints/AI-OPS-16/exports/declared_kpi_baseline.csv
rg -n "declared_total|declared_with_signal_pct" docs/etl/sprints/AI-OPS-16/exports/declared_kpi_baseline.csv
```

## Task 9 (P9 FAST) - Declared v3 tests

Run:

```bash
LOG="docs/etl/sprints/AI-OPS-16/evidence/declared-tests.log"
: > "$LOG"
if python3 -m unittest tests.test_parl_declared_stance tests.test_parl_review_queue tests.test_parl_declared_positions >> "$LOG" 2>&1; then
  echo "passed=true" >> "$LOG"
else
  echo "failed=true" >> "$LOG"
  exit 1
fi
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/declared-tests.log
rg -n "passed|failed" docs/etl/sprints/AI-OPS-16/evidence/declared-tests.log
```

## Task 10 (P10 FAST) - Backfill pass1 (control)

Run:

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance \
  --db "$DB_PATH" \
  --source-id "$SOURCE_ID" \
  --min-auto-confidence 0.62 \
  > docs/etl/sprints/AI-OPS-16/evidence/declared_backfill_pass1.log

sqlite3 -header -csv "$DB_PATH" "
SELECT 'declared_total' AS metric, COUNT(*) AS value
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'declared_with_signal',
       SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'declared_with_signal_pct',
       ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 6)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'review_pending', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID' AND status='pending'
UNION ALL
SELECT 'review_conflicting_signal', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID' AND status='pending' AND review_reason='conflicting_signal';
" > docs/etl/sprints/AI-OPS-16/exports/declared_pass1_metrics.csv
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/declared_backfill_pass1.log
test -f docs/etl/sprints/AI-OPS-16/exports/declared_pass1_metrics.csv
```

## Task 11 (P11 FAST) - Backfill pass2 (candidate)

Run:

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance \
  --db "$DB_PATH" \
  --source-id "$SOURCE_ID" \
  --min-auto-confidence 0.58 \
  > docs/etl/sprints/AI-OPS-16/evidence/declared_backfill_pass2.log

sqlite3 -header -csv "$DB_PATH" "
SELECT 'declared_total' AS metric, COUNT(*) AS value
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'declared_with_signal',
       SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'declared_with_signal_pct',
       ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 6)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'review_pending', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID' AND status='pending'
UNION ALL
SELECT 'review_conflicting_signal', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID' AND status='pending' AND review_reason='conflicting_signal';
" > docs/etl/sprints/AI-OPS-16/exports/declared_pass2_metrics.csv
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/declared_backfill_pass2.log
test -f docs/etl/sprints/AI-OPS-16/exports/declared_pass2_metrics.csv
```

## Task 12 (P12 FAST) - Select threshold + full apply

Run:

```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-16/evidence/declared_backfill_selected.log
import csv
from pathlib import Path

BASELINE_PCT = 0.32899
PASS = {
    'pass1': {'path': Path('docs/etl/sprints/AI-OPS-16/exports/declared_pass1_metrics.csv'), 'threshold': 0.62},
    'pass2': {'path': Path('docs/etl/sprints/AI-OPS-16/exports/declared_pass2_metrics.csv'), 'threshold': 0.58},
}

def load_metrics(path):
    out = {}
    with path.open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            out[str(row['metric'])] = float(row['value'])
    return out

rows = {name: load_metrics(cfg['path']) for name, cfg in PASS.items()}
eligible = {
    name: m for name, m in rows.items()
    if m.get('declared_with_signal_pct', -1.0) >= BASELINE_PCT
}

if not eligible:
    print('decision=NO-GO')
    print('reason=no pass meets declared_with_signal_pct floor')
    raise SystemExit(1)

selected = sorted(
    eligible.items(),
    key=lambda kv: (
        kv[1].get('declared_with_signal_pct', -1.0),
        kv[1].get('declared_with_signal', -1.0),
        -kv[1].get('review_pending', 0.0),
        -kv[1].get('review_conflicting_signal', 0.0),
        1 if kv[0] == 'pass1' else 0,
    ),
    reverse=True,
)[0][0]

print('decision=GO')
print(f'selected_pass={selected}')
print(f"selected_threshold={PASS[selected]['threshold']}")
print(f"selected_declared_with_signal_pct={eligible[selected].get('declared_with_signal_pct')}")
PY

SELECTED_THRESHOLD="$(rg '^selected_threshold=' docs/etl/sprints/AI-OPS-16/evidence/declared_backfill_selected.log | cut -d= -f2)"
python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance \
  --db "$DB_PATH" \
  --source-id "$SOURCE_ID" \
  --min-auto-confidence "$SELECTED_THRESHOLD" \
  >> docs/etl/sprints/AI-OPS-16/evidence/declared_backfill_selected.log

sqlite3 -header -csv "$DB_PATH" "
SELECT 'declared_total' AS metric, COUNT(*) AS value
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'declared_with_signal',
       SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'declared_with_signal_pct',
       ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 6)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='$SOURCE_ID'
UNION ALL
SELECT 'review_pending', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID' AND status='pending'
UNION ALL
SELECT 'review_conflicting_signal', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID' AND status='pending' AND review_reason='conflicting_signal';
" > docs/etl/sprints/AI-OPS-16/exports/declared_selected_metrics.csv
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/declared_backfill_selected.log
test -f docs/etl/sprints/AI-OPS-16/exports/declared_selected_metrics.csv
rg -n "decision=GO|selected_threshold=" docs/etl/sprints/AI-OPS-16/evidence/declared_backfill_selected.log
```

## Task 13 (P13 FAST) - Baseline vs selected diff matrix

Run:

```bash
python3 - <<'PY'
import csv
from pathlib import Path

base = Path('docs/etl/sprints/AI-OPS-16/exports/declared_kpi_baseline.csv')
sel = Path('docs/etl/sprints/AI-OPS-16/exports/declared_selected_metrics.csv')
out = Path('docs/etl/sprints/AI-OPS-16/exports/declared_diff_matrix.csv')

def load(path):
    d = {}
    with path.open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            d[str(row['metric'])] = float(row['value'])
    return d

b = load(base)
s = load(sel)
keys = sorted(set(b) | set(s))
with out.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['metric', 'baseline_value', 'selected_value', 'delta'])
    w.writeheader()
    for k in keys:
        bv = b.get(k, 0.0)
        sv = s.get(k, 0.0)
        w.writerow({'metric': k, 'baseline_value': bv, 'selected_value': sv, 'delta': sv - bv})
PY
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/exports/declared_diff_matrix.csv
rg -n "declared_with_signal|declared_with_signal_pct" docs/etl/sprints/AI-OPS-16/exports/declared_diff_matrix.csv
```

## Task 14 (P14 FAST) - Review queue snapshot

Run:

```bash
sqlite3 -header -csv "$DB_PATH" "
SELECT 'topic_evidence_reviews_total' AS metric, COUNT(*) AS value
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID'
UNION ALL
SELECT 'topic_evidence_reviews_pending', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID' AND status='pending'
UNION ALL
SELECT 'topic_evidence_reviews_resolved', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID' AND status='resolved'
UNION ALL
SELECT 'topic_evidence_reviews_ignored', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='$SOURCE_ID' AND status='ignored';
" > docs/etl/sprints/AI-OPS-16/exports/review_queue_snapshot.csv

{
  echo "# AI-OPS-16 review queue snapshot"
  date -u +"captured_at_utc=%Y-%m-%dT%H:%M:%SZ"
  cat docs/etl/sprints/AI-OPS-16/exports/review_queue_snapshot.csv
  echo
  echo "pending_by_reason"
  sqlite3 -header -csv "$DB_PATH" "
  SELECT COALESCE(review_reason,'(null)') AS review_reason, COUNT(*) AS c
  FROM topic_evidence_reviews
  WHERE source_id='$SOURCE_ID' AND status='pending'
  GROUP BY COALESCE(review_reason,'(null)')
  ORDER BY c DESC, review_reason ASC;
  "
} > docs/etl/sprints/AI-OPS-16/evidence/review_queue_snapshot.log
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/review_queue_snapshot.log
test -f docs/etl/sprints/AI-OPS-16/exports/review_queue_snapshot.csv
```

## Task 15 (P15 FAST) - Prepare review batch A with no-op path

Run:

```bash
PENDING_COUNT="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM topic_evidence_reviews WHERE source_id='$SOURCE_ID' AND status='pending';")"

if [ "$PENDING_COUNT" = "0" ]; then
  printf "evidence_id,source_id,review_reason,suggested_stance,suggested_confidence\n" > docs/etl/sprints/AI-OPS-16/exports/review_batch_a_input.csv
  {
    echo "pending_count=0"
    echo "no-op=true"
    echo "reason=empty pending review queue"
    echo "row_count=0"
  } > docs/etl/sprints/AI-OPS-16/evidence/review_batch_a_prep.log
else
  sqlite3 -header -csv "$DB_PATH" "
  SELECT evidence_id, source_id, review_reason, suggested_stance, suggested_confidence
  FROM topic_evidence_reviews
  WHERE source_id='$SOURCE_ID' AND status='pending'
  ORDER BY CASE review_reason
    WHEN 'conflicting_signal' THEN 1
    WHEN 'low_confidence' THEN 2
    WHEN 'no_signal' THEN 3
    WHEN 'missing_text' THEN 4
    ELSE 5 END,
    evidence_id ASC
  LIMIT 200;
  " > docs/etl/sprints/AI-OPS-16/exports/review_batch_a_input.csv

  ROW_COUNT="$(( $(wc -l < docs/etl/sprints/AI-OPS-16/exports/review_batch_a_input.csv) - 1 ))"
  {
    echo "pending_count=$PENDING_COUNT"
    echo "no-op=false"
    echo "row_count=$ROW_COUNT"
  } > docs/etl/sprints/AI-OPS-16/evidence/review_batch_a_prep.log
fi
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/review_batch_a_prep.log
test -f docs/etl/sprints/AI-OPS-16/exports/review_batch_a_input.csv
rg -n "row_count|no-op" docs/etl/sprints/AI-OPS-16/evidence/review_batch_a_prep.log
```

## Task 16 (P16 FAST) - Apply review batch A or no-op

Run:

```bash
BATCH_ROWS="$(( $(wc -l < docs/etl/sprints/AI-OPS-16/exports/review_batch_a_input.csv) - 1 ))"
DECISIONS_CSV="docs/etl/sprints/AI-OPS-16/exports/review_batch_a_decisions.csv"

if [ "$BATCH_ROWS" -le 0 ]; then
  {
    echo "no-op=true"
    echo "reason=review_batch_a_input.csv is empty"
    echo "resolved=0"
    echo "ignored=0"
  } > docs/etl/sprints/AI-OPS-16/evidence/review_batch_a_apply.log
else
  if [ ! -f "$DECISIONS_CSV" ]; then
    {
      echo "no-op=false"
      echo "failed=true"
      echo "reason=missing $DECISIONS_CSV"
    } > docs/etl/sprints/AI-OPS-16/evidence/review_batch_a_apply.log
    exit 1
  fi

  python3 - <<'PY' > docs/etl/sprints/AI-OPS-16/evidence/review_batch_a_apply.log
import csv
import json
import os
import subprocess
import sys

db_path = os.environ['DB_PATH']
source_id = os.environ['SOURCE_ID']
pos_as_of = os.environ['POS_AS_OF']
decisions = 'docs/etl/sprints/AI-OPS-16/exports/review_batch_a_decisions.csv'

resolved = 0
ignored = 0
for row in csv.DictReader(open(decisions, encoding='utf-8')):
    evidence_id = str(row.get('evidence_id', '')).strip()
    status = str(row.get('status', '')).strip()
    final_stance = str(row.get('final_stance', '')).strip()
    final_conf = str(row.get('final_confidence', '')).strip()
    note = str(row.get('note', 'ai-ops-16 batch a')).strip() or 'ai-ops-16 batch a'
    if not evidence_id or status not in ('resolved', 'ignored'):
        continue
    cmd = [
        'python3', 'scripts/ingestar_parlamentario_es.py', 'review-decision',
        '--db', db_path,
        '--source-id', source_id,
        '--evidence-ids', evidence_id,
        '--status', status,
        '--note', note,
        '--recompute',
        '--as-of-date', pos_as_of,
    ]
    if status == 'resolved' and final_stance in ('support', 'oppose', 'mixed', 'unclear', 'no_signal'):
        cmd.extend(['--final-stance', final_stance])
        if final_conf:
            cmd.extend(['--final-confidence', final_conf])
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        print('failed=true')
        print(f'evidence_id={evidence_id}')
        print(out.stdout)
        print(out.stderr)
        sys.exit(out.returncode)
    print(f'evidence_id={evidence_id}')
    print(out.stdout.strip())
    if status == 'resolved':
        resolved += 1
    else:
        ignored += 1

print(f'no-op=false')
print(f'resolved={resolved}')
print(f'ignored={ignored}')
PY
fi
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/review_batch_a_apply.log
rg -n "resolved|ignored|no-op" docs/etl/sprints/AI-OPS-16/evidence/review_batch_a_apply.log
```

## Task 17 (P17 FAST) - Recompute declared + combined positions

Run:

```bash
{
  echo "# AI-OPS-16 recompute positions"
  date -u +"captured_at_utc=%Y-%m-%dT%H:%M:%SZ"
  python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions \
    --db "$DB_PATH" \
    --source-id "$SOURCE_ID" \
    --as-of-date "$POS_AS_OF"

  python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions \
    --db "$DB_PATH" \
    --as-of-date "$POS_AS_OF"
} > docs/etl/sprints/AI-OPS-16/evidence/recompute_positions.log

sqlite3 -header -csv "$DB_PATH" "
SELECT computed_method, COUNT(*) AS positions_total
FROM topic_positions
WHERE as_of_date='$POS_AS_OF'
  AND computed_method IN ('votes','declared','combined')
GROUP BY computed_method
ORDER BY computed_method ASC;
" > docs/etl/sprints/AI-OPS-16/exports/topic_positions_post_declared.csv
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/recompute_positions.log
test -f docs/etl/sprints/AI-OPS-16/exports/topic_positions_post_declared.csv
```

## Task 18 (P18 FAST) - Coherence post packet

Run:

```bash
python3 - <<'PY' > docs/etl/sprints/AI-OPS-16/evidence/coherence_post.log
from pathlib import Path
from scripts.graph_ui_server import build_topics_coherence_payload

payload = build_topics_coherence_payload(Path('etl/data/staging/politicos-es.db'), limit=5, offset=0)
meta = payload.get('meta', {}) or {}
summary = payload.get('summary', {}) or {}
print('coherence_as_of_date', meta.get('as_of_date'))
print('coherence_overlap_total', summary.get('overlap_total'))
print('coherence_explicit_total', summary.get('explicit_total'))
print('coherence_coherent_total', summary.get('coherent_total'))
print('coherence_incoherent_total', summary.get('incoherent_total'))
PY

python3 - <<'PY'
import csv
from pathlib import Path
from scripts.graph_ui_server import build_topics_coherence_payload

payload = build_topics_coherence_payload(Path('etl/data/staging/politicos-es.db'), limit=5, offset=0)
meta = payload.get('meta', {}) or {}
summary = payload.get('summary', {}) or {}
rows = [
    {'metric': 'coherence_as_of_date', 'value': meta.get('as_of_date')},
    {'metric': 'coherence_overlap_total', 'value': summary.get('overlap_total')},
    {'metric': 'coherence_explicit_total', 'value': summary.get('explicit_total')},
    {'metric': 'coherence_coherent_total', 'value': summary.get('coherent_total')},
    {'metric': 'coherence_incoherent_total', 'value': summary.get('incoherent_total')},
]
out = Path('docs/etl/sprints/AI-OPS-16/exports/coherence_post.csv')
with out.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['metric', 'value'])
    w.writeheader()
    w.writerows(rows)
PY
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/coherence_post.log
test -f docs/etl/sprints/AI-OPS-16/exports/coherence_post.csv
```

## Task 19 (P19 FAST) - Blocker lever checks (anti-loop)

Run:

```bash
python3 - <<'PY'
import csv
import os
import socket
from pathlib import Path

aemet_key_present = 1 if str(os.getenv('AEMET_API_KEY', '')).strip() else 0
try:
    socket.gethostbyname('api.bde.es')
    bde_dns_resolves = 1
    bde_dns_error = ''
except Exception as exc:
    bde_dns_resolves = 0
    bde_dns_error = f'{type(exc).__name__}: {exc}'

galicia_policy = 1 if str(os.getenv('GALICIA_APPROVED_REPRO_BYPASS', '')).strip() == '1' else 0
navarra_policy = 1 if str(os.getenv('NAVARRA_APPROVED_REPRO_BYPASS', '')).strip() == '1' else 0

rows = [
    {
        'source_id': 'aemet_opendata_series',
        'new_lever_detected': int(aemet_key_present == 1),
        'decision': 'probe_allowed' if aemet_key_present == 1 else 'no_new_lever',
        'next_required_lever': 'AEMET_API_KEY in runtime' if aemet_key_present == 0 else 'run strict probe',
    },
    {
        'source_id': 'bde_series_api',
        'new_lever_detected': int(bde_dns_resolves == 1),
        'decision': 'probe_allowed' if bde_dns_resolves == 1 else 'no_new_lever',
        'next_required_lever': 'DNS resolution for api.bde.es' if bde_dns_resolves == 0 else 'run strict probe',
    },
    {
        'source_id': 'parlamento_galicia_deputados',
        'new_lever_detected': int(galicia_policy == 1),
        'decision': 'probe_allowed' if galicia_policy == 1 else 'no_new_lever',
        'next_required_lever': 'approved reproducible bypass policy',
    },
    {
        'source_id': 'parlamento_navarra_parlamentarios_forales',
        'new_lever_detected': int(navarra_policy == 1),
        'decision': 'probe_allowed' if navarra_policy == 1 else 'no_new_lever',
        'next_required_lever': 'approved reproducible bypass policy',
    },
]

strict_probes_executed = sum(1 for r in rows if r['decision'] == 'probe_allowed')
no_new_lever_count = sum(1 for r in rows if r['decision'] == 'no_new_lever')

matrix_out = Path('docs/etl/sprints/AI-OPS-16/exports/unblock_feasibility_matrix.csv')
with matrix_out.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['source_id', 'new_lever_detected', 'decision', 'next_required_lever'])
    w.writeheader()
    w.writerows(rows)

log_out = Path('docs/etl/sprints/AI-OPS-16/evidence/blocker-lever-check.log')
log_out.write_text(
    '\n'.join([
        '# AI-OPS-16 blocker lever check',
        f'AEMET_API_KEY_present={aemet_key_present}',
        f'bde_dns_resolves={bde_dns_resolves}',
        f'bde_dns_error={bde_dns_error}',
        f'galicia_approved_reproducible_bypass_policy={galicia_policy}',
        f'navarra_approved_reproducible_bypass_policy={navarra_policy}',
        f'strict_probes_executed={strict_probes_executed}',
        f'no_new_lever_count={no_new_lever_count}',
    ]) + '\n',
    encoding='utf-8',
)
PY
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/blocker-lever-check.log
test -f docs/etl/sprints/AI-OPS-16/exports/unblock_feasibility_matrix.csv
rg -n "strict_probes_executed|no_new_lever_count" docs/etl/sprints/AI-OPS-16/evidence/blocker-lever-check.log
```

## Task 20 (P20 FAST) - Strict gate, parity, reconciliation draft

Run:

```bash
python3 scripts/e2e_tracker_status.py \
  --db "$DB_PATH" \
  --tracker "$TRACKER_PATH" \
  --waivers "$WAIVERS_PATH" \
  --as-of-date "$GATE_AS_OF" \
  > docs/etl/sprints/AI-OPS-16/evidence/tracker-status-postrun.log

python3 scripts/e2e_tracker_status.py \
  --db "$DB_PATH" \
  --tracker "$TRACKER_PATH" \
  --waivers "$WAIVERS_PATH" \
  --as-of-date "$GATE_AS_OF" \
  --fail-on-mismatch \
  --fail-on-done-zero-real \
  > docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-postrun.log

python3 scripts/export_explorer_sources_snapshot.py \
  --db "$DB_PATH" \
  --out docs/etl/sprints/AI-OPS-16/evidence/status-postrun.json

python3 scripts/export_explorer_sources_snapshot.py \
  --db "$DB_PATH" \
  --out docs/gh-pages/explorer-sources/data/status.json

python3 - <<'PY' > docs/etl/sprints/AI-OPS-16/evidence/status-parity-postrun.txt
import json
from pathlib import Path
final = json.loads(Path('docs/etl/sprints/AI-OPS-16/evidence/status-postrun.json').read_text(encoding='utf-8'))
published = json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))
checks = [
  ('summary.tracker.mismatch', ('summary','tracker','mismatch')),
  ('summary.tracker.waived_mismatch', ('summary','tracker','waived_mismatch')),
  ('summary.tracker.done_zero_real', ('summary','tracker','done_zero_real')),
  ('summary.tracker.waivers_expired', ('summary','tracker','waivers_expired')),
  ('analytics.impact.indicator_series_total', ('analytics','impact','indicator_series_total')),
  ('analytics.impact.indicator_points_total', ('analytics','impact','indicator_points_total')),
]

def pick(obj, path):
    cur = obj
    for key in path:
        cur = (cur or {}).get(key)
    return cur

all_match = True
print('# AI-OPS-16 status parity summary')
for name, path in checks:
    fv = pick(final, path)
    pv = pick(published, path)
    ok = fv == pv
    all_match = all_match and ok
    print(f'{name}: final={fv} published={pv} match={str(ok).lower()}')
print(f'overall_match={str(all_match).lower()}')
PY

python3 - <<'PY'
from pathlib import Path

gate_log = Path('docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-postrun.log').read_text(encoding='utf-8')
parity = Path('docs/etl/sprints/AI-OPS-16/evidence/status-parity-postrun.txt').read_text(encoding='utf-8')

def extract(label, text):
    for line in text.splitlines():
        if line.lower().startswith(label.lower() + ':'):
            return line.split(':', 1)[1].strip()
    return ''

mismatches = extract('mismatches', gate_log)
waivers_expired = extract('waivers_expired', gate_log)
done_zero_real = extract('done_zero_real', gate_log)
overall_match = ''
for line in parity.splitlines():
    if line.startswith('overall_match='):
        overall_match = line.split('=', 1)[1].strip()
        break

content = """# AI-OPS-16 reconciliation draft

## Postrun gate snapshot
- mismatches: {mismatches}
- waivers_expired: {waivers_expired}
- done_zero_real: {done_zero_real}
- overall_match: {overall_match}

## Inputs
- docs/etl/sprints/AI-OPS-16/exports/declared_diff_matrix.csv
- docs/etl/sprints/AI-OPS-16/exports/coherence_post.csv
- docs/etl/sprints/AI-OPS-16/evidence/blocker-lever-check.log
- docs/etl/sprints/AI-OPS-16/evidence/status-parity-postrun.txt

## Decision placeholder
- decision: pending Task 21 review.
- escalation: if strict gate != 0 or overall_match != true.
""".format(
    mismatches=mismatches or 'n/a',
    waivers_expired=waivers_expired or 'n/a',
    done_zero_real=done_zero_real or 'n/a',
    overall_match=overall_match or 'n/a',
)
Path('docs/etl/sprints/AI-OPS-16/reports/reconciliation-draft.md').write_text(content, encoding='utf-8')
PY
```

Acceptance:

```bash
test -f docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-postrun.log
test -f docs/etl/sprints/AI-OPS-16/evidence/status-postrun.json
test -f docs/etl/sprints/AI-OPS-16/reports/reconciliation-draft.md
rg -n "mismatches|waivers_expired|done_zero_real" docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-postrun.log
```

## Escalation rule (Task 7)

Escalate immediately if any task cannot be executed with deterministic acceptance checks.

No-op policy summary:
- Task 15: explicit `no-op` when pending queue is zero.
- Task 16: explicit `no-op` when batch input is empty.
- Blocker lane remains `no_new_lever` unless new lever is detected.
