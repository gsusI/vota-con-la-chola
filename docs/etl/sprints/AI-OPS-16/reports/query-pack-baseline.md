# AI-OPS-16 Query Pack Baseline

Date:
- `2026-02-17`

Purpose:
- Provide deterministic baseline queries/commands for declared-signal KPIs, review queue metrics, coherence snapshot, strict tracker checks, and status export parity.

Scope:
- Primary lane: `congreso_intervenciones` declared signal + review loop + coherence/positions observability.
- Shared gates: strict tracker gate + status parity.

## Runtime Context

- DB: `etl/data/staging/politicos-es.db`
- Tracker: `docs/etl/e2e-scrape-load-tracker.md`
- Waivers: `docs/etl/mismatch-waivers.json`
- As-of date for checker: `2026-02-17`
- Sprint root: `docs/etl/sprints/AI-OPS-16/`

## 1) Declared Signal KPIs (Baseline)

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
"
```

Output contract:
- `docs/etl/sprints/AI-OPS-16/evidence/declared-baseline-metrics.csv`

## 2) Review Queue KPIs

```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "
SELECT 'topic_evidence_reviews_total' AS metric, COUNT(*) AS value
FROM topic_evidence_reviews
UNION ALL
SELECT 'topic_evidence_reviews_pending', COUNT(*)
FROM topic_evidence_reviews
WHERE status='pending'
UNION ALL
SELECT 'topic_evidence_reviews_resolved', COUNT(*)
FROM topic_evidence_reviews
WHERE status='resolved'
UNION ALL
SELECT 'topic_evidence_reviews_ignored', COUNT(*)
FROM topic_evidence_reviews
WHERE status='ignored';
"
```

Pending-by-reason (deterministic):

```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "
SELECT COALESCE(review_reason,'(null)') AS review_reason, COUNT(*) AS c
FROM topic_evidence_reviews
WHERE status='pending'
GROUP BY COALESCE(review_reason,'(null)')
ORDER BY c DESC, review_reason;
"
```

Output contract:
- `docs/etl/sprints/AI-OPS-16/evidence/review-queue-baseline-metrics.csv`
- `docs/etl/sprints/AI-OPS-16/exports/review_queue_pending_by_reason_baseline.csv`

## 3) Coherence Snapshot KPIs

```bash
python3 - <<'PY'
from pathlib import Path
from scripts.graph_ui_server import build_topics_coherence_payload
p = Path('etl/data/staging/politicos-es.db')
coh = build_topics_coherence_payload(p, limit=5, offset=0)
meta = coh.get('meta', {}) or {}
s = coh.get('summary', {}) or {}
print('coherence_as_of_date', meta.get('as_of_date'))
print('coherence_overlap_total', s.get('overlap_total'))
print('coherence_explicit_total', s.get('explicit_total'))
print('coherence_coherent_total', s.get('coherent_total'))
print('coherence_incoherent_total', s.get('incoherent_total'))
PY
```

Output contract:
- `docs/etl/sprints/AI-OPS-16/evidence/coherence-baseline.log`

## 4) Tracker Status + Strict Gate

Status checker:

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17
```

Strict gate:

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17 \
  --fail-on-mismatch \
  --fail-on-done-zero-real
```

Output contract:
- `docs/etl/sprints/AI-OPS-16/evidence/baseline-gate.log`
- `docs/etl/sprints/AI-OPS-16/evidence/tracker-status-pre.log`
- `docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-pre.log`

## 5) Status Export + Parity Inputs

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-16/evidence/status-pre.json

python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json
```

Key parity fields to compare:
- `summary.tracker.mismatch`
- `summary.tracker.waived_mismatch`
- `summary.tracker.done_zero_real`
- `summary.tracker.waivers_expired`
- `analytics.impact.indicator_series_total`
- `analytics.impact.indicator_points_total`

Output contract:
- `docs/etl/sprints/AI-OPS-16/evidence/status-pre.json`
- `docs/etl/sprints/AI-OPS-16/evidence/status-parity-pre.txt`

## 6) Tracker Mix (DONE/PARTIAL/TODO)

```bash
python3 - <<'PY'
from pathlib import Path
text = Path('docs/etl/e2e-scrape-load-tracker.md').read_text(encoding='utf-8')
counts = {'DONE': 0, 'PARTIAL': 0, 'TODO': 0}
for line in text.splitlines():
    if not line.startswith('| ') or line.startswith('| Tipo de dato') or line.startswith('|---'):
        continue
    parts = [p.strip() for p in line.strip('|').split('|')]
    if len(parts) >= 4 and parts[3] in counts:
        counts[parts[3]] += 1
for k in ('DONE', 'PARTIAL', 'TODO'):
    print(f'{k}={counts[k]}')
PY
```

Output contract:
- `docs/etl/sprints/AI-OPS-16/evidence/tracker-status-counts.txt`

## 7) Optional Convenience Commands

Use `just` wrappers when running inside Dockerized flow:

```bash
just etl-tracker-status
just etl-tracker-gate
```

## Acceptance Checklist

- File contains explicit command blocks for:
  - declared signal KPI extraction
  - review queue KPIs
  - coherence snapshot
  - `e2e_tracker_status.py` status and strict variants
  - `export_explorer_sources_snapshot.py`
- Baseline gate artifacts exist and report `status_exit=0`, `gate_exit=0`.
- Declared baseline CSV includes `declared_with_signal_pct`.
- Review queue baseline includes `topic_evidence_reviews_pending`.
