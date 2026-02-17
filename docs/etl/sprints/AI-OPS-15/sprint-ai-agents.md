# AI-OPS-15 Sprint Prompt Pack

## Objective
- Deliver visible, controllable progress in analytics/product truth while time-boxing external blocker probes and preserving strict gate/parity.

## Note (post-hoc metadata)
- This sprint predates the LONG_10X prompt-pack template used in later sprints (AI-OPS-17+).
- The "no blind retries" blocker policy is now canonical in `AGENTS.md` under **Anti-Loop Sprint Policy**.
- Any points metadata here is an estimate for planning only (do not treat as an executed measurement).

## Scale Metadata (post-hoc, estimated)
- `scale_mode`: `STANDARD_1X`
- `planned_points_estimate`: `15`
- `planned_task_count`: `7`
- `horizon_weeks`: `1`

## Tasks

1. Baseline capture
- Re-run tracker status/gate and snapshot blocker matrix for in-scope sources.
- Output: `docs/etl/sprints/AI-OPS-15/evidence/baseline-gate.log`
- Output: `docs/etl/sprints/AI-OPS-15/evidence/baseline-partial-sources.csv`

2. Delivery lane baseline (topic positions visibility)
- Capture baseline KPI packet for tracker line `78` (`Posiciones por tema`) before recompute.
- Output: `docs/etl/sprints/AI-OPS-15/exports/topic_positions_kpi_baseline.csv`
- Output: `docs/etl/sprints/AI-OPS-15/evidence/topic_positions_baseline.log`

3. Delivery lane execution (controllable)
- Run reproducible topic analytics recompute for latest as-of and record post-run metrics.
- Output: `docs/etl/sprints/AI-OPS-15/evidence/topic_positions_recompute.log`
- Output: `docs/etl/sprints/AI-OPS-15/exports/topic_positions_kpi_post.csv`

4. Delivery lane reconciliation (tracker + visibility)
- Update tracker line `78` with refreshed evidence, explicit delta, and next command based on post-run metrics.
- Output: `docs/etl/sprints/AI-OPS-15/reports/topic_positions_reconciliation.md`

5. Blocker lane (time-boxed, no-repeat policy)
- Probe remaining external blockers only when a new lever exists; otherwise record `no_new_lever` with evidence and skip repeated retries.
- Output: `docs/etl/sprints/AI-OPS-15/evidence/blocker-probe-refresh.log`
- Output: `docs/etl/sprints/AI-OPS-15/exports/unblock_feasibility_matrix.csv`

6. Final gate + parity
- Re-run strict gate and status export parity checks.
- Output: `docs/etl/sprints/AI-OPS-15/reports/final-gate-parity.md`

7. Closeout decision
- Publish PASS/FAIL against visible-progress gate first, then unblock carryover policy.
- Output: `docs/etl/sprints/AI-OPS-15/closeout.md`

## Acceptance

- `test -f docs/etl/sprints/AI-OPS-15/closeout.md`
- `rg -n "Sprint Verdict|Gate|next sprint trigger" docs/etl/sprints/AI-OPS-15/closeout.md`
