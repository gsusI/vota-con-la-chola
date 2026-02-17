# AI-OPS-13 T5 Final Gate + Parity

Date:
- `2026-02-17`

Objective:
- Re-run strict tracker gate and verify status export parity against SQL totals after reconciliation apply.

## Inputs used

- `docs/etl/sprints/AI-OPS-13/reports/reconciliation-apply.md`
- `docs/etl/sprints/AI-OPS-13/evidence/tracker-status-postreconcile.log`
- `docs/etl/sprints/AI-OPS-13/evidence/tracker-gate-postreconcile.log`
- `docs/etl/e2e-scrape-load-tracker.md`
- `etl/data/staging/politicos-es.db`

## Commands run

1. Final status checker:

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17
```

2. Final strict gate:

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17 \
  --fail-on-mismatch \
  --fail-on-done-zero-real
```

3. Final status export snapshots:

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-13/evidence/status-final.json

python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json
```

4. Final integrity and queue snapshots:

```bash
python3 - <<'PY'
import csv, sqlite3
conn = sqlite3.connect("etl/data/staging/politicos-es.db")
def exists(name): return conn.execute(
    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
    (name,),
).fetchone() is not None
def count(name): return 0 if not exists(name) else conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
row = {
  "fk_violations": conn.execute("SELECT COUNT(*) FROM pragma_foreign_key_check").fetchone()[0],
  "indicator_series_total": count("indicator_series"),
  "indicator_points_total": count("indicator_points"),
  "indicator_observation_records_total": count("observation_records"),
  "policy_events_total": count("policy_events"),
}
with open("docs/etl/sprints/AI-OPS-13/evidence/final-integrity-metrics.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(row.keys())); w.writeheader(); w.writerow(row)
conn.close()
PY

sqlite3 -csv -header etl/data/staging/politicos-es.db "SELECT COUNT(*) ... topic_evidence_reviews_pending ..."
```

## Evidence artifacts

- `docs/etl/sprints/AI-OPS-13/evidence/tracker-status-final.log`
- `docs/etl/sprints/AI-OPS-13/evidence/tracker-gate-final.log`
- `docs/etl/sprints/AI-OPS-13/evidence/tracker-gate-final.exit`
- `docs/etl/sprints/AI-OPS-13/evidence/status-final.json`
- `docs/etl/sprints/AI-OPS-13/evidence/status-parity-summary.txt`
- `docs/etl/sprints/AI-OPS-13/evidence/final-integrity-metrics.csv`
- `docs/etl/sprints/AI-OPS-13/evidence/final-review-queue.csv`

## Final metrics

Tracker/gate:
- strict gate exit code: `0`
- `mismatches=0`
- `waived_mismatches=0`
- `waivers_expired=0`
- `done_zero_real=0`

Integrity/queue:
- `fk_violations=0`
- `topic_evidence_reviews_pending=0`

Impact totals (SQL):
- `indicator_series_total=2400`
- `indicator_points_total=37431`
- `indicator_observation_records_total=0` (table absent in current DB snapshot; value recorded via table-safe metric capture)
- `policy_events_total=548`

Status payload (`status-final.json`):
- `summary.tracker.mismatch=0`
- `summary.tracker.waived_mismatch=0`
- `summary.tracker.done_zero_real=0`
- `summary.tracker.waivers_expired=0`
- `analytics.impact.indicator_series_total=2400`
- `analytics.impact.indicator_points_total=37431`

Published parity (`status-parity-summary.txt`):
- `overall_match=true` for tracker summary keys and impact counters between:
  - `docs/etl/sprints/AI-OPS-13/evidence/status-final.json`
  - `docs/gh-pages/explorer-sources/data/status.json`

## Baseline -> final delta (AI-OPS-13)

Compared with Task 1 baseline (`baseline-gate.log`):
- strict gate exit: `0 -> 0`
- `mismatches`: `0 -> 0`
- `waivers_expired`: `0 -> 0`
- `done_zero_real`: `0 -> 0`

Scope outcome:
- in-scope `PARTIAL` count: `6 -> 4`
- in-scope `DONE` count: `0 -> 2`
- transitioned to `DONE`: `bdns_api_subvenciones`, `bdns_autonomico`

Parity/integrity drift:
- `fk_violations`: `0 -> 0`
- `topic_evidence_reviews_pending`: `0 -> 0`
- `indicator_series_total`: `2400 -> 2400`
- `indicator_points_total`: `37431 -> 37431`

## Final parity verdict

- Gate `G3` is green with strict checker exit `0`.
- Gate `G4` parity is green: status impact counters are non-null and SQL-aligned.
- Gate `G1`/`G2` remain green (`fk_violations=0`, pending review queue `0`).

## Escalation rule check

T5 escalation condition:
- escalate if strict gate is green but status export tracker/impact keys are out of parity with SQL or published payload.

Observed:
- strict gate green and parity checks all matched.

Decision:
- `NO_ESCALATION`.
