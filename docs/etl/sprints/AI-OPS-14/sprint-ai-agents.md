# AI-OPS-14 Sprint Prompt Pack

## Objective
- Convert at least one remaining blocked source to evidence-backed `DONE` while keeping strict gate/parity green.

## Tasks

1. Baseline capture
- Re-run tracker status/gate and snapshot blocker matrix for in-scope sources.
- Output: `docs/etl/sprints/AI-OPS-14/evidence/baseline-gate.log`

2. Blocker probe refresh (remaining set)
- Re-probe remaining blockers (`waf`, `dns`, `contract/auth`) with strict-network-first evidence.
- Output: `docs/etl/sprints/AI-OPS-14/evidence/blocker-probe-refresh.log`

3. Mitigation feasibility matrix
- Build per-source unblock strategy with deterministic acceptance criteria and risk notes.
- Output: `docs/etl/sprints/AI-OPS-14/exports/unblock_feasibility_matrix.csv`

4. Targeted unblock execution wave
- Execute highest-feasibility unblock attempts and capture strict-network evidence.
- Output: `docs/etl/sprints/AI-OPS-14/evidence/unblock-execution.log`

5. Reconciliation apply (policy-aligned)
- Apply tracker updates only for sources with direct strict-network success evidence; keep others `PARTIAL` with refreshed blockers.
- Output: `docs/etl/sprints/AI-OPS-14/reports/reconciliation-apply.md`

6. Final gate + parity
- Re-run strict gate and status export parity checks.
- Output: `docs/etl/sprints/AI-OPS-14/reports/final-gate-parity.md`

7. Closeout decision
- Publish PASS/FAIL against unblock outcome gate and carryover policy.
- Output: `docs/etl/sprints/AI-OPS-14/closeout.md`

## Acceptance

- `test -f docs/etl/sprints/AI-OPS-14/closeout.md`
- `rg -n "Sprint Verdict|Gate|next sprint trigger" docs/etl/sprints/AI-OPS-14/closeout.md`
