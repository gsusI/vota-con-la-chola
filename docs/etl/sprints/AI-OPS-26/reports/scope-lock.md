# AI-OPS-26 Scope Lock

Date:
- 2026-02-19

Primary objective:
- Execute one end-to-end factory cycle and ship a measurable user-visible delta by applying Lane A decisions and recomputing declared+combined outputs.

In scope:
- `lane_a`: full execution (prep -> workers -> adjudication -> apply -> recompute).
- `lane_b`, `lane_c`, `lane_d`, `lane_e`: import-ready proposal packets and QA.
- `blocker` lane: bounded strict-network retry evidence for blocked sources.
- Postrun KPI + citizen/explorer artifact refresh and evidence capture.

Out of scope:
- Schema migrations and policy-method changes.
- Unlimited unblock retries.
- Any destructive DB rollback flow.

## Controllable vs Blocker Budget

- controllable points: `280`
- blocker points: `8`
- total planned points: `288`
- controllable share: `97.2%`
- blocker share: `2.8%`

Policy:
- Keep sprint execution `>=70%` controllable work.
- Keep blocker probe lane bounded to one strict retry per blocked source unless a new lever appears.

## Gate Contract

- `G1` Contract gate:
  - PASS when all lane artifacts match exact headers/enums/nullability in `factory-contract-v2.md`.
- `G2` Lane A execution gate:
  - PASS when `topic_evidence_reviews.pending` decreases after Lane A apply.
- `G3` Recompute gate:
  - PASS when declared+combined recompute logs exist and complete without errors.
- `G4` Factory throughput gate:
  - PASS when lanes B/C/D/E each emit `tasks_input.csv`, `workers_raw*`, `decisions_adjudicated.csv`, `qa_report.md`.
- `G5` Blocker honesty gate:
  - PASS when each blocked source has at most one strict retry and explicit `no_new_lever` when unchanged.
- `G6` Parity gate:
  - PASS when tracker status reports `mismatches=0` and `done_zero_real=0`.
- `G7` Citizen artifact gate:
  - PASS when citizen snapshots validate and stay within `5,000,000` byte budget.
- `G8` Visible progress gate:
  - PASS when at least one measurable KPI delta is published in `exports/kpi_delta.csv`.

## Batch Naming and Immutability

Batch naming:
- `factory-YYYYMMDD-lane_<letter>-<seq>`
- Example: `factory-20260219-lane_a-001`

Immutability rules:
- `workers_raw*.csv` are append-only and never edited after first write.
- Corrections happen only in `decisions_adjudicated.csv` plus `qa_report.md`.
- Every output row must include stable unit IDs + traceability source columns.

## Execution Stop Conditions

Stop and escalate to L3 if:
- Any gate cannot be evaluated due missing artifact contracts.
- A lane requires schema/policy changes to proceed.
- Blocker lane requests repeated probes with no new lever.
