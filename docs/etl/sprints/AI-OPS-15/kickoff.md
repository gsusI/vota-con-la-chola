# AI-OPS-15 Kickoff

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Scope Lock

Single sprint objective:
- Deliver one visible, controllable progress delta (analytics/product truth) while preserving strict tracker gate and publish/status parity; keep external unblock attempts as a time-boxed secondary lane.

## Baseline (from AI-OPS-15 step 1 capture)

Tracker/gate:
- strict status exit: `0`
- strict gate exit: `0`
- `mismatches=0`
- `waivers_expired=0`
- `done_zero_real=0`

Carryover blocker set:
- `parlamento_galicia_deputados`
- `parlamento_navarra_parlamentarios_forales`
- `bde_series_api`
- `aemet_opendata_series`

Primary delivery row:
- line `78`: `Posiciones por tema (politico x scope)` (`PARTIAL`)

In-scope row snapshot (`baseline-partial-sources.csv`):
- `parlamento_galicia_deputados`: `runs_ok_total=5/12`, `max_net=0`, `last_loaded=0`
- `parlamento_navarra_parlamentarios_forales`: `runs_ok_total=3/12`, `max_net=50`, `last_loaded=0`
- `bde_series_api`: `runs_ok_total=3/11`, `max_net=0`, `last_loaded=0`
- `aemet_opendata_series`: `runs_ok_total=3/12`, `max_net=0`, `last_loaded=0`

## In-scope rows/sources

Primary lane:
- line `78`: `Posiciones por tema (politico x scope)`

Secondary lane (time-boxed blockers):
- line `45`: `parlamento_galicia_deputados`
- line `53`: `parlamento_navarra_parlamentarios_forales`
- line `67`: `bde_series_api`
- line `68`: `aemet_opendata_series`

Out of scope:
- sources already `DONE` unless regression appears.

## Must-pass gates (AI-OPS-15)

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

`G5` Visible progress gate (primary):
- pass only if tracker line `78` gets an evidence-backed measurable delta (coverage/KPI refresh and updated reconciliation narrative).

`G6` Unblock outcome gate (secondary):
- pass if at least one blocker source transitions `PARTIAL -> DONE` with reproducible strict-network evidence (`exit 0`, `run_records_loaded>0`).
- if no new unblock lever exists, `G6` may remain neutral, but evidence must explicitly record `no_new_lever` decisions.

## Execution policy

- No fake completion.
- Preserve truthful blockers and executable next commands for rows that remain blocked.
- Do not loop blind retries for external blockers; retries require a new lever.
- If blocker lane has no new lever, spend capacity on primary controllable delivery lane.
