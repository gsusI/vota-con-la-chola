# KPI Acceptance Pack (T5)

Purpose:
- Define PASS/FAIL checks for AI-OPS-26 closeout using deterministic queries and artifact checks.

DB:
- `etl/data/staging/politicos-es.db`

## KPI-1: lane_a queue reduction

Definition:
- `pending_before` and `pending_after` for `programas_partidos` review queue.

Query:
```sql
SELECT COUNT(*) AS pending
FROM topic_evidence_reviews
WHERE source_id='programas_partidos' AND status='pending';
```

PASS:
- `pending_after < pending_before`

Evidence files:
- `docs/etl/sprints/AI-OPS-26/evidence/lane_a_before.txt`
- `docs/etl/sprints/AI-OPS-26/evidence/lane_a_after.txt`

## KPI-2: lane_a decisions applied

Definition:
- Number of reviewed rows changed to `resolved|ignored` for lane_a batch IDs.

Query:
```sql
SELECT status, COUNT(*) AS c
FROM topic_evidence_reviews
WHERE source_id='programas_partidos'
GROUP BY status
ORDER BY status;
```

PASS:
- `resolved_after + ignored_after > resolved_before + ignored_before`

Evidence files:
- `docs/etl/sprints/AI-OPS-26/exports/factory/lane_a/post_apply_metrics.csv`
- `docs/etl/sprints/AI-OPS-26/reports/lane_a_apply.md`

## KPI-3: recompute freshness

Definition:
- Declared/combined positions recomputed at target `as_of_date`.

Query:
```sql
SELECT computed_method, MAX(as_of_date) AS max_as_of_date, COUNT(*) AS rows_total
FROM topic_positions
WHERE computed_method IN ('declared','combined')
GROUP BY computed_method
ORDER BY computed_method;
```

PASS:
- `max_as_of_date >= AS_OF_DATE` for both methods.
- `rows_total > 0` for both methods.

Evidence files:
- `docs/etl/sprints/AI-OPS-26/evidence/lane_a_recompute.log`

## KPI-4: tracker parity integrity

Command:
```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json
```

PASS:
- `mismatches = 0`
- `done_zero_real = 0`
- `waivers_expired = 0`

Evidence files:
- `docs/etl/sprints/AI-OPS-26/evidence/status-postrun.json`

## KPI-5: citizen artifact validation and size budget

Commands:
```bash
python3 scripts/export_citizen_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/citizen/data/citizen.json \
  --topic-set-id 1 \
  --computed-method combined \
  --max-bytes 5000000

python3 scripts/validate_citizen_snapshot.py \
  --path docs/gh-pages/citizen/data/citizen.json \
  --max-bytes 5000000 \
  --strict-grid

wc -c docs/gh-pages/citizen/data/citizen.json
```

PASS:
- validator exits `0`
- citizen size `<= 5000000` bytes

Evidence files:
- `docs/etl/sprints/AI-OPS-26/evidence/citizen-validate.txt`
- `docs/etl/sprints/AI-OPS-26/evidence/citizen-json-size.txt`

## KPI-6: visible progress publish check

Definition:
- A measurable delta is published in sprint exports and referenced in closeout.

PASS:
- `docs/etl/sprints/AI-OPS-26/exports/kpi_delta.csv` exists.
- File includes at least one row where `metric_before != metric_after`.

Evidence files:
- `docs/etl/sprints/AI-OPS-26/exports/kpi_delta.csv`
- `docs/etl/sprints/AI-OPS-26/closeout.md`

## KPI execution checklist

1. Capture baseline counters before apply.
2. Run lane_a apply and recompute.
3. Re-run counters and compute deltas.
4. Re-run parity checker and persist status.
5. Rebuild/validate citizen artifacts and record size.
6. Write `kpi_delta.csv` and reference it in closeout.
