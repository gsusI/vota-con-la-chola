# AI-OPS-16 Task 6: Setup Wave Signoff

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Setup completeness check

Required setup artifacts (Tasks 1-5):
- `docs/etl/sprints/AI-OPS-16/reports/scope-lock.md` -> `OK`
- `docs/etl/sprints/AI-OPS-16/reports/query-pack-baseline.md` -> `OK`
- `docs/etl/sprints/AI-OPS-16/reports/declared-stance-v3-design.md` -> `OK`
- `docs/etl/sprints/AI-OPS-16/reports/declared-stance-v3-tests.md` -> `OK`
- `docs/etl/sprints/AI-OPS-16/reports/kpi-acceptance-pack.md` -> `OK`

Required baseline evidence:
- `docs/etl/sprints/AI-OPS-16/evidence/baseline-gate.log` -> `OK`
- `docs/etl/sprints/AI-OPS-16/evidence/declared-baseline-metrics.csv` -> `OK`
- `docs/etl/sprints/AI-OPS-16/evidence/review-queue-baseline-metrics.csv` -> `OK`
- `docs/etl/sprints/AI-OPS-16/evidence/tracker-status-counts.txt` -> `OK`

Setup wave completeness verdict:
- `PASS`

## Frozen gates (FAST wave)

Hard gates (must pass):
- `H1` strict gate: exit `0`; `mismatches=0`; `waivers_expired=0`; `done_zero_real=0`.
- `H2` integrity: `fk_violations=0`.
- `H3` publish/status parity: `overall_match=true` for required tracker/impact keys.
- `H4` scope invariant: `declared_total` remains `614` during this sprint wave.

Delivery gates:
- `D1` threshold selection uses deterministic policy from `kpi-acceptance-pack.md`.
- `D2` visible progress: pass only if declared signal/coherence improves vs baseline.
- `D3` closeout queue health: `topic_evidence_reviews_pending=0`.

## Escalation policy (frozen)

Immediate `NO-GO`:
- any hard gate fails.
- `overall_match=false`.
- both candidate passes fail threshold/quality acceptance.

Escalate but continue truthful reporting:
- no measurable `D2` delta after selected run/recompute.
- blocker lane has no new lever: keep `no_new_lever` and skip blind retries.
- strict gate/parity mismatch unresolved after postrun evidence capture.

## lane execution order (locked)

HI setup lane:
- Tasks `1 -> 2 -> 3 -> 4 -> 5 -> 6` completed.

Next HI handoff:
- Task `7` (`fast-wave-checklist.md`) must complete before FAST run tasks.

FAST lane sequence (by dependency groups):
- `P8` + `P9` (baseline + tests)
- `P10` + `P11` (dual declared backfill passes)
- `P12` (selected threshold full apply)
- `P13` + `P14` (diff matrix + review queue snapshot)
- `P15 -> P16` (review batch prep/apply with explicit no-op path)
- `P17 -> P18` (recompute + coherence post packet)
- `P19` (blocker lever checks, anti-loop policy)
- `P20` (strict gate + parity + reconciliation draft)

## GO / NO-GO decision

Current setup-wave decision:
- `GO` for Task `7` and FAST wave execution under frozen gates.

NO-GO fallback trigger:
- if any required setup artifact above is missing or malformed before Task `7` starts.

Signoff:
- `GO` approved.
