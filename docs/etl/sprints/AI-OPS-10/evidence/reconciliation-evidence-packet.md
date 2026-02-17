# AI-OPS-10 Reconciliation Evidence Packet

Date:
- `2026-02-17`

## Scope
- Assemble final L1 packet for HI reconciliation and close wave handoff (T27).
- Packet covers AI-OPS-10 artifacts produced through T26: strict/replay applies, recomputes, parity snapshots, tracker/gate evidence, waiver candidates, status export parity, tracker row draft, and blocker refresh.

## Packet Index

- Reports (`22` files):
  - `docs/etl/sprints/AI-OPS-10/reports/aemet-apply.md`
  - `docs/etl/sprints/AI-OPS-10/reports/aemet-contract-hardening.md`
  - `docs/etl/sprints/AI-OPS-10/reports/batch-prep.md`
  - `docs/etl/sprints/AI-OPS-10/reports/bde-apply.md`
  - `docs/etl/sprints/AI-OPS-10/reports/bde-contract-hardening.md`
  - `docs/etl/sprints/AI-OPS-10/reports/bdns-replay-run.md`
  - `docs/etl/sprints/AI-OPS-10/reports/bdns-strict-run.md`
  - `docs/etl/sprints/AI-OPS-10/reports/contract-schema-normalization.md`
  - `docs/etl/sprints/AI-OPS-10/reports/contract-tests.md`
  - `docs/etl/sprints/AI-OPS-10/reports/eurostat-apply.md`
  - `docs/etl/sprints/AI-OPS-10/reports/eurostat-contract-hardening.md`
  - `docs/etl/sprints/AI-OPS-10/reports/hi-handoff-runbook.md`
  - `docs/etl/sprints/AI-OPS-10/reports/indicator-recompute.md`
  - `docs/etl/sprints/AI-OPS-10/reports/placsp-bdns-snapshot-adapter.md`
  - `docs/etl/sprints/AI-OPS-10/reports/placsp-replay-run.md`
  - `docs/etl/sprints/AI-OPS-10/reports/placsp-strict-run.md`
  - `docs/etl/sprints/AI-OPS-10/reports/policy-events-recompute.md`
  - `docs/etl/sprints/AI-OPS-10/reports/probe-matrix-generator.md`
  - `docs/etl/sprints/AI-OPS-10/reports/status-export-parity.md`
  - `docs/etl/sprints/AI-OPS-10/reports/strict-probe-runner.md`
  - `docs/etl/sprints/AI-OPS-10/reports/throughput-blockers-refresh.md`
  - `docs/etl/sprints/AI-OPS-10/reports/waiver-candidates.md`
- Exports (`4` files):
  - `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv`
  - `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
  - `docs/etl/sprints/AI-OPS-10/exports/tracker_row_patch_plan.tsv`
  - `docs/etl/sprints/AI-OPS-10/exports/waiver_candidates_ai_ops_10.csv`
- Root evidence files (`6` files):
  - `docs/etl/sprints/AI-OPS-10/evidence/status-postrun.json`
  - `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-mismatch-sources.csv`
  - `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.log`
  - `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.md`
  - `docs/etl/sprints/AI-OPS-10/evidence/tracker-row-reconciliation-draft.md`
  - `docs/etl/sprints/AI-OPS-10/evidence/tracker-status-postrun.log`
- Evidence directories (file counts):
  - `docs/etl/sprints/AI-OPS-10/evidence/aemet`: `13` files
  - `docs/etl/sprints/AI-OPS-10/evidence/aemet-logs`: `6` files
  - `docs/etl/sprints/AI-OPS-10/evidence/aemet-sql`: `6` files
  - `docs/etl/sprints/AI-OPS-10/evidence/bde`: `13` files
  - `docs/etl/sprints/AI-OPS-10/evidence/bde-logs`: `6` files
  - `docs/etl/sprints/AI-OPS-10/evidence/bde-sql`: `6` files
  - `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay`: `17` files
  - `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay-logs`: `8` files
  - `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay-sql`: `8` files
  - `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict`: `9` files
  - `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-logs`: `4` files
  - `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql`: `4` files
  - `docs/etl/sprints/AI-OPS-10/evidence/eurostat`: `13` files
  - `docs/etl/sprints/AI-OPS-10/evidence/eurostat-logs`: `6` files
  - `docs/etl/sprints/AI-OPS-10/evidence/eurostat-sql`: `6` files
  - `docs/etl/sprints/AI-OPS-10/evidence/indicator-recompute-sql`: `21` files
  - `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay`: `17` files
  - `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay-logs`: `8` files
  - `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay-sql`: `8` files
  - `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict`: `9` files
  - `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-logs`: `4` files
  - `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql`: `4` files
  - `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql`: `11` files
  - `docs/etl/sprints/AI-OPS-10/evidence/probe-runner-dryrun`: `2` files
  - `docs/etl/sprints/AI-OPS-10/evidence/replay-inputs`: `7` files
  - `docs/etl/sprints/AI-OPS-10/evidence/snapshot-adapter`: `2` files
  - `docs/etl/sprints/AI-OPS-10/evidence/source-parity-sql`: `8` files

## Completeness Check

Mandatory artifact set validated (T13-T26 wave):
- total mandatory artifacts: `21`
- missing artifacts: `0`
- missing list: `(none)`

## Tracker and Status Snapshot

From `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.log`:
- `tracker_sources=35`
- `sources_in_db=42`
- `mismatches=3`
- `done_zero_real=0`
- `waivers_expired=0`

Tracker mismatch source_ids: `eurostat_sdmx, placsp_autonomico, placsp_sindicacion`

From `docs/etl/sprints/AI-OPS-10/evidence/status-postrun.json`:
- `analytics.impact.indicator_series_total=2400`
- `analytics.impact.indicator_points_total=37431`
- `summary.tracker.mismatch=3`
- `summary.tracker.done_zero_real=0`
- `summary.tracker.waivers_expired=0`

## HI Handoff Summary

Status for HI reconciliation wave:
- tracker gate remains `FAIL` because `mismatches=3`
- parity evidence is complete and reproducible for all carryover families (strict/from-file/replay snapshots present).
- blocker taxonomy is refreshed in `docs/etl/sprints/AI-OPS-10/reports/throughput-blockers-refresh.md` with per-source `root_cause` and `next command`.

Ready HI decisions (inputs for T28-T30):
- waiver candidates prepared: `APPLY_TEMP_WAIVER=2`, `DONT_APPLY_RECONCILE_TRACKER=1` (`docs/etl/sprints/AI-OPS-10/exports/waiver_candidates_ai_ops_10.csv`).
- tracker row patch plan prepared: `UPDATE_STATUS=1`, `KEEP_STATUS=6` (`docs/etl/sprints/AI-OPS-10/exports/tracker_row_patch_plan.tsv`).
- proposed status transition with strongest parity evidence: `eurostat_sdmx` (`PARTIAL -> DONE`).
- blocked rows kept `PARTIAL` with explicit blocker and next command: PLACSP/BDNS/BDE/AEMET rows.

Expected post-HI outcomes to validate in T29:
- re-run `just etl-tracker-gate` after tracker reconciliation changes.
- confirm `fk_violations=0` and status export parity (`indicator_series_total`, `indicator_points_total`).

## Escalation Rule Check

T27 escalation condition:
- escalate if packet completeness check fails for any mandatory artifact.

Observed:
- mandatory artifacts present: `21/21`
- missing mandatory artifacts: `0`

Decision:
- `NO_ESCALATION`.
