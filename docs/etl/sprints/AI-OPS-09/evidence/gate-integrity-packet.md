# Gate and integrity packet (AI-OPS-09)

## Inputs
- Outputs from money-policy-events recompute and indicator harmonization recompute.
- SQLite DB: `etl/data/staging/politicos-es.db`.
- Tracker references:
  - `docs/etl/e2e-scrape-load-tracker.md`
  - `docs/etl/mismatch-waivers.json`

## Commands executed
1. `DB_PATH=etl/data/staging/politicos-es.db just etl-tracker-status`
2. `DB_PATH=etl/data/staging/politicos-es.db just etl-tracker-gate --fail-on-mismatch --fail-on-done-zero-real`
3. `sqlite3 etl/data/staging/politicos-es.db "PRAGMA foreign_key_check;"`
4. Review queue SQL checks on `topic_evidence_reviews`.
5. Policy-events and indicator totals SQL checks.

## Artifact logs
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-tracker-status.log`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-tracker-gate.log`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-tracker-status-postreconcile.log`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-tracker-gate-postreconcile.log`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-fk-check.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-review-queue.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-policy_events_by_source.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-policy_events_by_source_full.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-policy_events_total.txt`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-policy_events_total_full.txt`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-indicator_series_count.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-indicator_points_count.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-indicator_series_by_source.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-indicator_points_null_by_source.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-mismatch-sources.txt`

## Strict tracker status
Captured output in:
- `gate-integrity-tracker-status.log` (pre-reconciliation)
- `gate-integrity-tracker-status-postreconcile.log` (final)

Final summary (post-reconciliation):
- `tracker_sources: 35`
- `sources_in_db: 42`
- `mismatches: 0`
- `waived_mismatches: 0`
- `waivers_active: 0`
- `waivers_expired: 0`
- `done_zero_real: 0`

## Strict gate
Captured output in:
- `gate-integrity-tracker-gate.log` (pre-reconciliation)
- `gate-integrity-tracker-gate-postreconcile.log` (final)

Final result (post-reconciliation):
- Exit code file line: `EXIT_CODE=0`
- No strict-policy errors (`mismatches=0`, `waivers_expired=0`, `done_zero_real=0`).

## Foreign key integrity
`gate-integrity-fk-check.csv`:

```csv
metric,value
foreign_key_violations,0
```

`PRAGMA foreign_key_check` produced no violations.

## Review queue integrity
`gate-integrity-review-queue.csv`:

```csv
metric,value
topic_evidence_reviews_pending,0
topic_evidence_reviews_resolved,50
topic_evidence_reviews_ignored,474
topic_evidence_reviews_total,524
```

## Policy-events snapshot (post-recompute)
- `gate-integrity-policy_events_total_full.txt` -> `total_policy_events = 548`
- `gate-integrity-policy_events_by_source_full.csv` (non-zero rows shown):
  - `bdns_subvenciones,5`
  - `boe_api_legal,298`
  - `moncloa_referencias,20`
  - `moncloa_rss_referencias,8`
  - `placsp_contratacion,217`

- `gate-integrity-policy_events_by_source.csv` (target sources)
  - `aemet_opendata_series: 0`
  - `bde_series_api: 0`
  - `eurostat_sdmx: 0`
  - `bdns_subvenciones: 5`
  - `placsp_contratacion: 217`

## Indicator snapshot (post-recompute)
- `indicator_series_count`: `2400`
- `indicator_points_count`: `37431`

`gate-integrity-indicator_series_by_source.csv`:
- `aemet_opendata_series,2`
- `bde_series_api,2`
- `eurostat_sdmx,2396`

`gate-integrity-indicator_points_null_by_source.csv`:
- `aemet_opendata_series,6,0,6`
- `bde_series_api,6,0,6`
- `eurostat_sdmx,37419,0,37419`

## Integrity summary
- Foreign-key: clean (`0` violations).
- Review queue: non-empty but all terminal (`pending=0`).
- Integrity of recompute outputs: indicators and policy-events are populated with non-zero counts and source-level traceability rows.
- Strict gate status: **PASS**, with `mismatches=0`, `waivers_expired=0`, `done_zero_real=0` and `waived_mismatches=0`.

## Gate-ready evidence checklist
- [x] status command run
- [x] strict gate command run with pass output captured
- [x] FK check and queue check executed
- [x] post-recompute policy_events and indicators totals captured
- [x] tracker reconciliation applied and revalidated against strict gate
