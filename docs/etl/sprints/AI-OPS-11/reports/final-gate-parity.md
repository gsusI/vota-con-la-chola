# AI-OPS-11 T5 Final Gate + Parity

Date:
- `2026-02-17`

Objective:
- Re-run strict tracker gate and verify status export parity against SQL totals after reconciliation apply.

## Inputs used

- `docs/etl/sprints/AI-OPS-11/reports/reconciliation-apply.md`
- `docs/etl/sprints/AI-OPS-11/evidence/tracker-status-postreconcile.log`
- `docs/etl/sprints/AI-OPS-11/evidence/tracker-gate-postreconcile.log`
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
  --out docs/etl/sprints/AI-OPS-11/evidence/status-final.json

python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json
```

4. Final integrity and queue snapshots:

```bash
sqlite3 -csv -header etl/data/staging/politicos-es.db "SELECT ... fk_violations, indicator_series_total, indicator_points_total ..."
sqlite3 -csv -header etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"
```

## Evidence artifacts

- `docs/etl/sprints/AI-OPS-11/evidence/tracker-status-final.log`
- `docs/etl/sprints/AI-OPS-11/evidence/tracker-gate-final.log`
- `docs/etl/sprints/AI-OPS-11/evidence/tracker-gate-final.exit`
- `docs/etl/sprints/AI-OPS-11/evidence/status-final.json`
- `docs/etl/sprints/AI-OPS-11/evidence/status-parity-summary.txt`
- `docs/etl/sprints/AI-OPS-11/evidence/final-integrity-metrics.csv`
- `docs/etl/sprints/AI-OPS-11/evidence/final-review-queue.csv`

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
- `indicator_observation_records_total=37431`
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
  - `docs/etl/sprints/AI-OPS-11/evidence/status-final.json`
  - `docs/gh-pages/explorer-sources/data/status.json`

## Baseline -> final delta (AI-OPS-11)

Compared with Task 1 baseline (`baseline-gate.log`):
- strict gate exit: `1 -> 0`
- `mismatches`: `2 -> 0`
- mismatch sources: `placsp_autonomico`, `placsp_sindicacion` -> none
- `waivers_expired`: `0 -> 0`
- `done_zero_real`: `0 -> 0`

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
