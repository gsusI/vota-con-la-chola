# AI-OPS-13 Sprint Prompt Pack

## Objective
- Convert at least one blocked source to evidence-backed `DONE` while keeping strict gate/parity green.

## Tasks

1. Baseline capture
- Re-run tracker status/gate and snapshot blocker matrix for in-scope sources.
- Output: `docs/etl/sprints/AI-OPS-13/evidence/baseline-gate.log`

2. Mitigation feasibility matrix
- Build per-source unblock strategy (`waf`, `anti-bot`, `dns`, `contract`) with deterministic acceptance criteria and risk notes.
- Output: `docs/etl/sprints/AI-OPS-13/exports/unblock_feasibility_matrix.csv`

3. Targeted unblock execution wave
- Execute highest-feasibility unblock attempts and capture strict-network evidence.
- Output: `docs/etl/sprints/AI-OPS-13/evidence/unblock-execution.log`

4. Reconciliation apply (policy-aligned)
- Apply tracker updates only for sources with direct strict-network success evidence; keep others `PARTIAL` with refreshed blockers.
- Output: `docs/etl/sprints/AI-OPS-13/reports/reconciliation-apply.md`

5. Final gate + parity
- Re-run strict gate and status export parity checks.
- Output: `docs/etl/sprints/AI-OPS-13/reports/final-gate-parity.md`

6. Closeout decision
- Publish PASS/FAIL against unblock outcome gate and carryover policy.
- Output: `docs/etl/sprints/AI-OPS-13/closeout.md`

## Acceptance

- `test -f docs/etl/sprints/AI-OPS-13/closeout.md`
- `rg -n "Sprint Verdict|Gate|next sprint trigger" docs/etl/sprints/AI-OPS-13/closeout.md`
