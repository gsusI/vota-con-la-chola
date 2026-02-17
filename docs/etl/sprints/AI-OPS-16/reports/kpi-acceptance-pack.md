# AI-OPS-16 Task 5: KPI Acceptance Pack

Date:
- `2026-02-17`

Objective:
- Define deterministic acceptance thresholds for FAST wave decisions (Tasks 8-20), with fail-fast behavior for declared signal, strict gate, coherence, and status parity.

## Inputs

- `docs/etl/sprints/AI-OPS-16/reports/query-pack-baseline.md`
- `docs/etl/sprints/AI-OPS-16/reports/declared-stance-v3-design.md`
- `docs/etl/sprints/AI-OPS-16/reports/declared-stance-v3-tests.md`
- `docs/etl/sprints/AI-OPS-16/evidence/declared-baseline-metrics.csv`
- `docs/etl/sprints/AI-OPS-16/evidence/review-queue-baseline-metrics.csv`
- `docs/etl/sprints/AI-OPS-16/evidence/baseline-gate.log`
- `docs/etl/sprints/AI-OPS-16/kickoff.md`

## Baseline constants (lock)

Declared signal (`congreso_intervenciones`):
- `declared_total_baseline=614`
- `declared_with_signal_baseline=202`
- `declared_with_signal_pct_baseline=0.32899`

Strict gate baseline:
- `strict_gate_exit_baseline=0`
- `mismatches_baseline=0`
- `waivers_expired_baseline=0`
- `done_zero_real_baseline=0`

Coherence baseline (for final adjudication):
- `coherence_overlap_total_baseline=82`
- `coherence_explicit_total_baseline=58`
- `coherence_coherent_total_baseline=33`
- `coherence_incoherent_total_baseline=25`

## Gate contract

### Hard gates (must pass)

`H1` strict gate:
- strict gate command exits `0`.
- counters remain `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`.

`H2` integrity:
- `fk_violations=0`.

`H3` parity:
- parity summary reports `overall_match=true` for required keys.
- required keys:
  - `summary.tracker.mismatch`
  - `summary.tracker.waived_mismatch`
  - `summary.tracker.done_zero_real`
  - `summary.tracker.waivers_expired`
  - `analytics.impact.indicator_series_total`
  - `analytics.impact.indicator_points_total`

`H4` scope invariant:
- `declared_total` must remain `614` in this wave (no new ingest scope).

### Delivery gates

`D1` threshold-selection gate (Task 12):
- choose candidate pass (`pass1` vs `pass2`) that maximizes `declared_with_signal_pct`.
- non-regression floor: selected `declared_with_signal_pct >= 0.32899`.
- tie-breakers (deterministic):
  1. larger `declared_with_signal`
  2. lower `review_pending`
  3. lower pending `conflicting_signal`
  4. fallback `pass1`

`D2` visible progress gate (final):
- pass if at least one condition is true:
  - `declared_with_signal > 202`, or
  - `declared_with_signal_pct > 0.32899`, or
  - (`coherence_explicit_total > 58` and `coherence_coherent_total >= 33`).

`D3` queue closeout gate:
- `topic_evidence_reviews_pending=0` at closeout (after review/apply loop).

## Fail-fast checks

Stop FAST lane immediately (`NO-GO`) if any occurs:
- strict gate non-zero exit or non-zero `mismatches`/`waivers_expired`/`done_zero_real`.
- parity file reports `overall_match=false`.
- `fk_violations>0`.
- selected candidate has `declared_with_signal_pct < 0.32899`.
- both `pass1` and `pass2` fail hard gates.

Escalate (do not fake DONE):
- no candidate satisfies hard gates.
- visible progress gate `D2` fails after selected run + recompute.
- blocker-lane pressure appears but no new lever exists; keep `no_new_lever` path and continue primary lane only.

## Command pack

### 1) Declared KPI extraction (baseline/pass1/pass2/selected)

```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "
SELECT 'declared_total' AS metric, COUNT(*) AS value
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones'
UNION ALL
SELECT 'declared_with_signal',
       SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones'
UNION ALL
SELECT 'declared_with_signal_pct',
       ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 6)
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones';
" > docs/etl/sprints/AI-OPS-16/exports/declared_<label>_metrics.csv
```

### 2) Strict gate command (hard gate H1)

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17 \
  --fail-on-mismatch \
  --fail-on-done-zero-real \
  > docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-postrun.log
```

### 3) Integrity + queue checks (H2, D3)

```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "
SELECT 'fk_violations' AS metric, COUNT(*) AS value FROM pragma_foreign_key_check
UNION ALL
SELECT 'topic_evidence_reviews_pending', COUNT(*)
FROM topic_evidence_reviews
WHERE lower(status)='pending';
" > docs/etl/sprints/AI-OPS-16/exports/integrity_queue_postrun.csv
```

### 4) Status parity and `overall_match` (H3)

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-16/evidence/status-postrun.json

python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json

python3 - <<'PY' > docs/etl/sprints/AI-OPS-16/evidence/status-parity-postrun.txt
import json
from pathlib import Path
final = json.loads(Path('docs/etl/sprints/AI-OPS-16/evidence/status-postrun.json').read_text(encoding='utf-8'))
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
print('# AI-OPS-16 status parity summary')
for name, path in checks:
    fv = pick(final, path)
    pv = pick(published, path)
    match = fv == pv
    overall_match = overall_match and match
    print(f'{name}: final={fv} published={pv} match={str(match).lower()}')
print(f'overall_match={str(overall_match).lower()}')
PY
```

### 5) Pass selection policy (Task 12)

```bash
python3 - <<'PY'
import csv, json
from pathlib import Path

BASELINE_PCT = 0.32899


def load_metrics(path):
    data = {}
    with Path(path).open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            data[str(row['metric'])] = float(row['value'])
    return data

p1 = load_metrics('docs/etl/sprints/AI-OPS-16/exports/declared_pass1_metrics.csv')
p2 = load_metrics('docs/etl/sprints/AI-OPS-16/exports/declared_pass2_metrics.csv')

cand = {
    'pass1': p1,
    'pass2': p2,
}

eligible = {k: v for k, v in cand.items() if v.get('declared_with_signal_pct', -1.0) >= BASELINE_PCT}
if not eligible:
    decision = {'selected': None, 'decision': 'NO-GO', 'reason': 'no pass meets declared_with_signal_pct floor'}
else:
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
    decision = {'selected': selected, 'decision': 'GO', 'reason': 'max declared_with_signal_pct with deterministic tie-break'}

print(json.dumps(decision, ensure_ascii=True, sort_keys=True, indent=2))
PY
```

## Acceptance result format (required fields in postrun notes)

- `declared_with_signal_pct` (baseline, selected, delta)
- `strict gate` exit + counters
- `overall_match`
- `fk_violations`
- `topic_evidence_reviews_pending`
- final decision: `GO` or `NO-GO`

## Escalation rule check (Task 5)

- Condition: KPI targets conflict with anti-loop or data-integrity policy.
- Outcome: no conflict found. The pack preserves strict gate/parity hard gates, keeps blocker lane on `no_new_lever`, and uses deterministic threshold selection.
- Decision: `NO_ESCALATION`.
