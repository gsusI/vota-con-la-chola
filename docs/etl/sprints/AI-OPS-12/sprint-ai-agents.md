# AI-OPS-12 Sprint Prompt Pack

## Objective
- Burn down remaining blocker debt for `PARTIAL` sources while keeping strict gate and publish parity green.

## Tasks

1. Baseline capture
- Re-run tracker status/gate and snapshot current `PARTIAL` source matrix.
- Output: `docs/etl/sprints/AI-OPS-12/evidence/baseline-gate.log`

2. Blocker probe refresh
- Re-run strict-network probes for in-scope sources and capture latest blocker signatures.
- Output: `docs/etl/sprints/AI-OPS-12/evidence/blocker-probe-refresh.log`

3. Source decision packet
- Build deterministic per-source recommendation (`KEEP_PARTIAL`, `RECONCILE_TO_DONE`, `WAIVER_CANDIDATE`) with evidence links.
- Output: `docs/etl/sprints/AI-OPS-12/exports/source_decision_packet.csv`

4. Reconciliation apply (policy-aligned)
- Apply only evidence-backed tracker updates from task 3 (status transitions only when strict success is proven).
- Output: `docs/etl/sprints/AI-OPS-12/reports/reconciliation-apply.md`

5. Final gate + parity
- Re-run strict gate and status export parity checks.
- Output: `docs/etl/sprints/AI-OPS-12/reports/final-gate-parity.md`

6. Closeout decision
- Publish PASS/FAIL with unresolved blocker carryover and next trigger.
- Output: `docs/etl/sprints/AI-OPS-12/closeout.md`

## Acceptance

- `test -f docs/etl/sprints/AI-OPS-12/closeout.md`
- `rg -n "Sprint Verdict|Gate|next sprint trigger" docs/etl/sprints/AI-OPS-12/closeout.md`
