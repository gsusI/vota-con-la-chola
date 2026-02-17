# AI-OPS-11 Kickoff

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Scope Lock

Single sprint objective:
- Resolve remaining PLACSP tracker mismatches (`placsp_autonomico`, `placsp_sindicacion`) and recover strict tracker gate (`G3`) without fake `DONE` transitions.

## Baseline (from AI-OPS-10 closeout)

Tracker/gate:
- strict gate exit: `1`
- `mismatches=2`
- mismatch sources: `placsp_autonomico`, `placsp_sindicacion`
- `done_zero_real=0`
- `waivers_expired=0`

Integrity and parity:
- `fk_violations=0`
- `topic_evidence_reviews_pending=0`
- `indicator_series_total=2400`
- `indicator_points_total=37431`

## In-scope rows/sources

- line `56`: `placsp_autonomico`
- line `64`: `placsp_sindicacion`

Out of scope:
- other carryover sources remain monitor-only unless regression appears.

## Must-pass gates (AI-OPS-11)

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
- If PLACSP strict-network remains blocked, resolution must be explicit policy (`waiver`) or explicit tracker/sql alignment choice with evidence.
- Preserve additive-only schema/docs updates.
