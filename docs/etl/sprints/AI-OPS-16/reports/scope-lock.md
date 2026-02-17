# AI-OPS-16 Scope Lock

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Objective

- Deliver a measurable declared-signal improvement slice for `congreso_intervenciones` with reproducible evidence and strict-gate safety.

## Why This Slice

- AI-OPS-15 closed `topic_positions` coverage blocker (`line 78`), so next highest-leverage controllable bottleneck is declared-signal quality (`docs/roadmap-tecnico.md`, Fase 2 says/declaradas path).
- External blockers remain unchanged; anti-loop policy keeps them secondary and bounded.

## Baseline Evidence

- `docs/etl/sprints/AI-OPS-16/evidence/baseline-gate.log`
- `docs/etl/sprints/AI-OPS-16/evidence/declared-baseline-metrics.csv`
- `docs/etl/sprints/AI-OPS-16/evidence/review-queue-baseline-metrics.csv`
- `docs/etl/sprints/AI-OPS-16/evidence/tracker-status-counts.txt`

Key baseline values:
- strict gate: `status_exit=0`, `gate_exit=0`
- declared signal: `202/614` (`0.32899`)
- tracker mix: `DONE=34`, `PARTIAL=4`, `TODO=9`
- pending review queue: `0`

## Lane Split

Primary lane (must deliver visible delta):
- declared stance improvements, deterministic backfill passes, recompute, postrun KPI delta and reconciliation.

Secondary lane (policy-bounded):
- four carryover external blockers (`Galicia`, `Navarra`, `BDE`, `AEMET`) handled via lever checks only unless new lever exists.

## Must-pass Gates

- `G1` Integrity: `fk_violations=0`
- `G2` Queue health: `topic_evidence_reviews_pending=0`
- `G3` Strict gate: `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`
- `G4` Status parity: final vs published payload parity holds
- `G5` Visible progress: declared-signal lane shows measurable delta with evidence
- `G6` Anti-loop blocker policy: `no_new_lever` path explicitly logged when applicable

## Escalation Rules

- Escalate if declared-signal changes require non-deterministic policy/arbitration decisions.
- Escalate if strict gate fails post-apply and root cause is not attributable with evidence.
- Escalate if any blocker source gains a new lever but cannot be executed reproducibly.

## GO Decision

- `GO`: setup wave may proceed to query-pack and implementation/testing packets.
