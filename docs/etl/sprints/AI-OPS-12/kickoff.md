# AI-OPS-12 Kickoff

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Scope Lock

Single sprint objective:
- Reduce blocker debt across remaining `PARTIAL` sources (`galicia`, `navarra`, `bdns_*`, `bde_series_api`, `aemet_opendata_series`) while preserving green strict tracker gate and publish/status parity.

## Baseline (from AI-OPS-11 closeout)

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

Current `PARTIAL` source set:
- `parlamento_galicia_deputados` (line `45`)
- `parlamento_navarra_parlamentarios_forales` (line `53`)
- `bdns_autonomico` (line `57`)
- `bdns_api_subvenciones` (line `65`)
- `bde_series_api` (line `67`)
- `aemet_opendata_series` (line `68`)

## In-scope rows/sources

- line `45`: `parlamento_galicia_deputados`
- line `53`: `parlamento_navarra_parlamentarios_forales`
- line `57`: `bdns_autonomico`
- line `65`: `bdns_api_subvenciones`
- line `67`: `bde_series_api`
- line `68`: `aemet_opendata_series`

Out of scope:
- rows already `DONE` unless regression appears.

## Must-pass gates (AI-OPS-12)

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

`G5` Reconciliation discipline:
- blocked sources stay `PARTIAL` unless a reproducible status transition is directly evidenced.

## Execution policy

- No fake completion.
- Every row update must include blocker signature + evidence path + executable next command.
- Prefer truthful blocker refresh (`PARTIAL`) over speculative `DONE`.
