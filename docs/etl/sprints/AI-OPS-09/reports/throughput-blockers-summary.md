# Throughput and Blocker Summary (AI-OPS-09 HI Closeout)

Date: 2026-02-17
Inputs:
- `docs/etl/sprints/AI-OPS-09/evidence/gate-integrity-packet.md`
- `docs/etl/sprints/AI-OPS-09/reports/publish-parity-check.md`
- `docs/etl/sprints/AI-OPS-09/evidence/replay-duplicate-audit.md`

## 1) Throughput summary and replay parity by source family

Source-level throughput is captured from `publish-parity-source-metrics-sql.csv` and replay status from `evidence/replay-duplicate-audit.md`.

| family | source_id | runs_ok | runs_total | records_loaded_any | records_loaded_network | records_loaded_fallback | replay_parity_status | blocker |
|---|---|---:|---:|---:|---:|---:|---|
| placsp | placsp_autonomico | 2 | 3 | 106 | 106 | 2 | NOT_COMPUTABLE | `metric,value` snapshot artifacts lack `run_records_loaded` fields, no numeric replay parity comparison |
| placsp | placsp_sindicacion | 5 | 7 | 106 | 106 | 3 | NOT_COMPUTABLE | `metric,value` snapshot artifacts lack `run_records_loaded` fields, no numeric replay parity comparison |
| bdns | bdns_api_subvenciones | 2 | 6 | 3 | 0 | 3 | NOT_COMPUTABLE | replay artifacts are `metric,value` only; replay counter parity could not be evaluated |
| bdns | bdns_autonomico | 1 | 3 | 2 | 0 | 2 | NOT_COMPUTABLE | replay artifacts are `metric,value` only; replay counter parity could not be evaluated |
| eurostat | eurostat_sdmx | 6 | 11 | 2394 | 2394 | 2 | FAIL | strict-network loaded 2394; replay/from-file recorded `exit_code=1` and `run_records_loaded=0` |
| bde | bde_series_api | 1 | 5 | 2 | 0 | 2 | NOT_APPLICABLE | strict-network and replay both failed (`exit_code=1`, `run_records_loaded=0`) so strict baseline replay parity is not meaningful |
| aemet | aemet_opendata_series | 1 | 5 | 2 | 0 | 2 | NOT_APPLICABLE | strict-network `404` and replay fixture resolution issues; both modes have `exit_code=1` and `run_records_loaded=0` |

## 2) Post-apply tracker and impact metrics

From `gate-integrity-packet.md` and `publish-parity-check.md`:
- tracker summary: `mismatch=7`, `waived_mismatch=0`, `done_zero_real=0`
- gate summary: `sources_in_db=42`, `tracker_sources=35`, `waivers_active=0`, `waivers_expired=0`
- tracker state totals (`summary.tracker`): `todo=16`, `partial=3`, `done=27`, `unmapped=13`, `untracked_sources=7`
- sql summary (`summary.sql`): `todo=2`, `partial=6`, `done=34`, `foreign_key_violations=0`
- integrity: `foreign_key_violations=0` and `topic_evidence_reviews_pending=0`
- impact payload (`analytics.impact`): `indicator_series_total=2400`, `indicator_points_total=37431`
- policy-events totals: `policy_events_total=548` with source contributions including `placsp_contratacion=217`, `boe_api_legal=298`, `moncloa_referencias=20`

## 3) Blocker classification (root cause)

| source_id | mismatch_state | root_cause | blocker_note | evidence |
|---|---|---|---|---|
| placsp_autonomico | MISMATCH | unknown | replay evidence is non-comparable due `metric,value` run snapshot schema | `evidence/replay-duplicate-audit.md` |
| placsp_sindicacion | MISMATCH | unknown | replay evidence is non-comparable due `metric,value` run snapshot schema | `evidence/replay-duplicate-audit.md` |
| bdns_api_subvenciones | MISMATCH | data_quality | replay/coverage counters missing in audit snapshot artifacts; parity cannot be proven numerically | `exports/bdns_ingest_matrix.csv`, `evidence/bdns-ingest-logs/sql/bdns_api_subvenciones__strict-network_run_snapshot.csv` |
| bdns_autonomico | MISMATCH | data_quality | replay/coverage counters missing in audit snapshot artifacts; parity cannot be proven numerically | `exports/bdns_ingest_matrix.csv`, `evidence/bdns-ingest-logs/sql/bdns_autonomico__strict-network_run_snapshot.csv` |
| eurostat_sdmx | MISMATCH | contract | strict-network succeeds, replay/from-file fail with zero loaded and exit code 1, suggesting strict/replay payload-path contract mismatch | `evidence/replay-duplicate-audit.md` |
| bde_series_api | MISMATCH | auth | strict-mode and replay network/replay path errors (`DNS/parseable series`), no successful baseline for replay diff | `evidence/replay-duplicate-audit.md` |
| aemet_opendata_series | MISMATCH | auth | strict-mode `HTTP 404` and replay fixture-path failures block deterministic replay | `evidence/replay-duplicate-audit.md` |

## 4) Unresolved items and HI closeout recommendation

- `Strict gate` remains **FAIL** (`EXIT_CODE=1`) because `mismatches=7`, `waived_mismatches=0`, and `done_zero_real=0`.
- `records_loaded` can be demonstrated for all source families in the matrix above, but replay parity is only verifiable for Eurostat (where it fails) and effectively blocked/not applicable for the rest.
- Duplicate key audit found zero duplicate `(source_id, source_record_id)` pairs; no replay-duplicate escalation from integrity constraints.
- HI closeout should remain `pending` until:
  1) strict-network/replay artifact schema is normalized for PLACSP/BDNS, and
  2) BDE/AEMET replay/parity blockers are resolved, or
  3) mismatch/waiver state is intentionally updated with evidence-backed blocker notes.
