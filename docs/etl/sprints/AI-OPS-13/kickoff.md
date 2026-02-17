# AI-OPS-13 Kickoff

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Scope Lock

Single sprint objective:
- Achieve at least one evidence-backed unblock transition (`PARTIAL -> DONE`) among remaining blocked sources while preserving strict tracker gate and publish/status parity.

## Baseline (from AI-OPS-12 closeout)

Tracker/gate:
- strict gate exit: `0`
- `mismatches=0`
- `waivers_expired=0`
- `done_zero_real=0`

Integrity and parity:
- `fk_violations=0`
- `topic_evidence_reviews_pending=0`
- `indicator_series_total=2400`
- `indicator_points_total=37431`

Carryover blocker set:
- `parlamento_galicia_deputados`
- `parlamento_navarra_parlamentarios_forales`
- `bdns_autonomico`
- `bdns_api_subvenciones`
- `bde_series_api`
- `aemet_opendata_series`

## In-scope rows/sources

- line `45`: `parlamento_galicia_deputados`
- line `53`: `parlamento_navarra_parlamentarios_forales`
- line `57`: `bdns_autonomico`
- line `65`: `bdns_api_subvenciones`
- line `67`: `bde_series_api`
- line `68`: `aemet_opendata_series`

Out of scope:
- sources already `DONE` unless regression appears.

## Must-pass gates (AI-OPS-13)

`G1` Integrity:
- `fk_violations=0`

`G2` Queue health:
- `topic_evidence_reviews_pending=0`

`G3` Tracker strict gate:
- `python3 scripts/e2e_tracker_status.py ... --fail-on-mismatch --fail-on-done-zero-real` exits `0` with:
  - `mismatches=0`
  - `waivers_expired=0`
  - `done_zero_real=0`

`G4` Publish/status parity:
- `analytics.impact.indicator_series_total` and `indicator_points_total` remain SQL-aligned and non-null.

`G5` Unblock outcome gate:
- pass only if at least one in-scope source transitions `PARTIAL -> DONE` with reproducible strict-network evidence (`exit 0`, `run_records_loaded>0`).

## Execution policy

- No fake completion.
- Preserve truthful blockers and executable next commands for rows that remain blocked.
- If no source can be unblocked, mark sprint `FAIL` even when G1-G4 remain green.
