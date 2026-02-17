# Publish parity check (AI-OPS-09)

## Objective
Refresh explorer snapshot payload and verify publish parity for new source families after money/indicator recomputes.

## Commands run
1. `python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/etl/sprints/AI-OPS-09/evidence/status-post-apply.json`
2. `python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json`
3. SQL parity queries executed in workspace (saved in evidence files):
   - `publish-parity-totals.csv`
   - `publish-parity-policy-events-by-source-focus.csv`
   - `publish-parity-source-metrics-sql.csv`
   - `publish-parity-matrix.json/csv`

## Snapshot snippets
### summary.tracker
```json
{
  "items_total": 46,
  "unmapped": 13,
  "todo": 16,
  "partial": 3,
  "done": 27,
  "mismatch": 7,
  "waived_mismatch": 0,
  "done_zero_real": 0,
  "untracked_sources": 7,
  "waivers_active": 0,
  "waivers_expired": 0,
  "waivers_error": ""
}
```

### analytics.impact
```json
{
  "causal_estimates_total": 0,
  "indicator_points_total": 37431,
  "indicator_series_total": 2400
}
```

### summary.sql
```json
{
  "todo": 2,
  "partial": 6,
  "done": 34,
  "foreign_key_violations": 0
}
```

## SQL totals (post-recompute)
- `policy_events_total`: `548`
- `indicator_series_total`: `2400`
- `indicator_points_total`: `37431`

`publish-parity-totals.csv`:
- `policy_events_total,548`
- `indicator_series_total,2400`
- `indicator_points_total,37431`

## Target source parity matrix
From `publish-parity-matrix.json` and `publish-parity-matrix.csv` for:
`placsp_autonomico`, `placsp_sindicacion`, `placsp_contratacion`, `bdns_api_subvenciones`, `bdns_autonomico`, `bdns_subvenciones`, `eurostat_sdmx`, `bde_series_api`, `aemet_opendata_series`:

| source_id | snapshot.tracker_status | snapshot.sql_status | snapshot.mismatch_state | snapshot.mismatch_waived | snapshot.waiver_expiry |
|---|---|---|---|---|---|
| placsp_autonomico | TODO | DONE | MISMATCH | false | (empty) |
| placsp_sindicacion | TODO | DONE | MISMATCH | false | (empty) |
| placsp_contratacion |  | TODO | UNTRACKED | false | (empty) |
| bdns_api_subvenciones | TODO | PARTIAL | MISMATCH | false | (empty) |
| bdns_autonomico | TODO | PARTIAL | MISMATCH | false | (empty) |
| bdns_subvenciones |  | TODO | UNTRACKED | false | (empty) |
| eurostat_sdmx | TODO | DONE | MISMATCH | false | (empty) |
| bde_series_api | TODO | PARTIAL | MISMATCH | false | (empty) |
| aemet_opendata_series | TODO | PARTIAL | MISMATCH | false | (empty) |

`publish-parity-source-metrics-sql.csv` shows SQL run/status metrics used for recomputation parity (runs, max_loaded_any, max_loaded_network, last_loaded) for the same IDs, and all rows were programmatically reconciled to the snapshot row values in `publish-parity-matrix.json`.

## Policy-events and indicator payload snippets
### policy events (SQL)
`publish-parity-policy-events-by-source-focus.csv`:
- `bdns_subvenciones,5`
- `boe_api_legal,298`
- `moncloa_referencias,20`
- `moncloa_rss_referencias,8`
- `placsp_contratacion,217`

### source ids in snapshot slice
`publish-parity-target-snapshot-slice.json` contains entries for all requested money/indicator families (`placsp`, `bdns`, `eurostat`, `bde`, `aemet`) with expected `mismatch_state`, `mismatch_waived`, and `waiver_expiry` values.

## Integrity outcome
- `mismatches` exist by design in `snapshot.mismatch_state` (`mismatch: 7`) for `placsp_autonomico`, `placsp_sindicacion`, `bdns_api_subvenciones`, `bdns_autonomico`, `eurostat_sdmx`, `bde_series_api`, `aemet_opendata_series`.
- No `waived` mismatches (`waiver_expiry` empty in all rows above).
- `foreign_key_violations` remains `0` in snapshot.

## Parity check verdict
- No field-level divergence detected between snapshot (`docs/etl/sprints/AI-OPS-09/evidence/status-post-apply.json`) and SQL-derived checks for the selected source IDs.
- Escalation not required by this parity step.

## Evidence artifacts
- `docs/etl/sprints/AI-OPS-09/evidence/status-post-apply.json`
- `docs/etl/sprints/AI-OPS-09/evidence/publish-parity-matrix.json`
- `docs/etl/sprints/AI-OPS-09/evidence/publish-parity-matrix.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/publish-parity-source-metrics-sql.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/publish-parity-policy-events-by-source-focus.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/publish-parity-totals.csv`
- `docs/etl/sprints/AI-OPS-09/evidence/publish-parity-target-snapshot-slice.json`
- `docs/etl/sprints/AI-OPS-09/evidence/publish-parity-analytics-impact-snippet.json`
- `docs/etl/sprints/AI-OPS-09/evidence/publish-parity-summary-tracker-snippet.json`
