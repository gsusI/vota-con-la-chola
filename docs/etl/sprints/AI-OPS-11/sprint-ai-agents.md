# AI-OPS-11 Sprint Prompt Pack

## Objective
- Clear remaining PLACSP mismatch debt and get strict tracker gate back to green with evidence-backed decisions.

## Tasks

1. Baseline capture
- Re-run tracker status/gate and snapshot mismatch sources.
- Output: `docs/etl/sprints/AI-OPS-11/evidence/baseline-gate.log`

2. PLACSP strict probe refresh
- Re-run strict probes for `placsp_autonomico` and `placsp_sindicacion`.
- Output: `docs/etl/sprints/AI-OPS-11/evidence/placsp-strict-refresh.log`

3. Waiver decision packet
- Build deterministic apply/don't-apply proposal for remaining PLACSP mismatches.
- Output: `docs/etl/sprints/AI-OPS-11/exports/placsp_waiver_decision.csv`

4. Reconciliation apply (policy-aligned)
- Apply only evidence-backed tracker/waiver updates decided in task 3.
- Output: `docs/etl/sprints/AI-OPS-11/reports/reconciliation-apply.md`

5. Final gate + parity
- Re-run strict gate and status export parity checks.
- Output: `docs/etl/sprints/AI-OPS-11/reports/final-gate-parity.md`

6. Closeout decision
- Publish PASS/FAIL with carryover policy and next trigger.
- Output: `docs/etl/sprints/AI-OPS-11/closeout.md`

## Acceptance

- `test -f docs/etl/sprints/AI-OPS-11/closeout.md`
- `rg -n "Sprint Verdict|Gate|next sprint trigger" docs/etl/sprints/AI-OPS-11/closeout.md`
