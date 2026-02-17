# AI-OPS-10 T29 Final Publish Parity

Date:
- `2026-02-17`

Objective:
- Confirm tracker, DB integrity, and status export parity after T28 tracker reconciliation.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/reports/tracker-reconciliation-final.md`
- `docs/etl/sprints/AI-OPS-10/evidence/status-postrun.json`
- `etl/data/staging/politicos-es.db`

## Commands run

1. Post-reconcile status checker:

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17
```

2. Post-reconcile strict gate:

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17 \
  --fail-on-mismatch \
  --fail-on-done-zero-real
```

3. Refresh status snapshot:

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-10/evidence/status-final.json
```

4. Integrity SQL snapshot:

```bash
sqlite3 -csv -header etl/data/staging/politicos-es.db "SELECT ... fk_violations, indicator_series_total, indicator_points_total ..."
```

## Evidence artifacts

- `docs/etl/sprints/AI-OPS-10/evidence/tracker-status-final.log`
- `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-final.log`
- `docs/etl/sprints/AI-OPS-10/evidence/status-final.json`
- `docs/etl/sprints/AI-OPS-10/evidence/final-integrity-metrics.csv`

## Final metrics

Tracker/gate:
- `mismatches=2`
- `done_zero_real=0`
- `waivers_expired=0`
- strict gate exit code: `1` (`FAIL: checklist/sql mismatches detected`)

Remaining mismatch source_ids:
- `placsp_autonomico`
- `placsp_sindicacion`

Integrity/parity:
- `fk_violations=0`
- `indicator_series_total=2400`
- `indicator_points_total=37431`
- `indicator_observation_records_total=37431`
- `policy_events_total=548`

Status payload (`status-final.json`):
- `summary.tracker.mismatch=2`
- `summary.tracker.done_zero_real=0`
- `summary.tracker.waivers_expired=0`
- `analytics.impact.indicator_series_total=2400`
- `analytics.impact.indicator_points_total=37431`

## Pre/Post reconciliation delta

Compared to T22 postrun baseline:
- `mismatches`: `3 -> 2`
- mismatch source set: removed `eurostat_sdmx`
- `fk_violations`: `0 -> 0`
- `indicator_series_total`: `2400 -> 2400`
- `indicator_points_total`: `37431 -> 37431`

## Final parity verdict

- Status export and SQL totals are aligned for impact keys (`indicator_series_total`, `indicator_points_total`).
- No new DB integrity regression detected (`fk_violations=0`).
- Tracker strict gate still fails due two unresolved PLACSP mismatches.

## Escalation rule check

T29 escalation condition:
- escalate if a new integrity regression appears after tracker reconciliation.

Observed:
- no new integrity regression (`fk_violations` stayed `0`; indicator totals unchanged).

Decision:
- `NO_ESCALATION`.
