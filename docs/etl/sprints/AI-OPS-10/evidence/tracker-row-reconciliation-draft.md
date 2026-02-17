# AI-OPS-10 T25 Tracker Row Reconciliation Draft

Date:
- `2026-02-17`

Objective:
- Prepare an evidence-backed row patch proposal (`DONE/PARTIAL/TODO`) for carryover tracker rows using postrun gate evidence and waiver candidate output.

## Inputs used

- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.md`
- `docs/etl/sprints/AI-OPS-10/evidence/status-postrun.json`
- `docs/etl/sprints/AI-OPS-10/exports/waiver_candidates_ai_ops_10.csv`

## Scope guard

Target rows only (non-target rows untouched):
- line `56` (`placsp_autonomico`)
- line `57` (`bdns_autonomico`)
- line `64` (`placsp_sindicacion`)
- line `65` (`bdns_api_subvenciones`)
- line `66` (`eurostat_sdmx`)
- line `67` (`bde_series_api`)
- line `68` (`aemet_opendata_series`)

## Patch proposal summary

| tracker_line | source_id | current_tracker | sql_status_postrun | mismatch_state | proposed_tracker | waiver_candidate | action |
|---|---|---|---|---|---|---|---|
| 56 | `placsp_autonomico` | `PARTIAL` | `DONE` | `MISMATCH` | `PARTIAL` | `APPLY_TEMP_WAIVER` | `KEEP_STATUS` |
| 57 | `bdns_autonomico` | `PARTIAL` | `PARTIAL` | `MATCH` | `PARTIAL` | `NOT_NEEDED` | `KEEP_STATUS` |
| 64 | `placsp_sindicacion` | `PARTIAL` | `DONE` | `MISMATCH` | `PARTIAL` | `APPLY_TEMP_WAIVER` | `KEEP_STATUS` |
| 65 | `bdns_api_subvenciones` | `PARTIAL` | `PARTIAL` | `MATCH` | `PARTIAL` | `NOT_NEEDED` | `KEEP_STATUS` |
| 66 | `eurostat_sdmx` | `PARTIAL` | `DONE` | `MISMATCH` | `DONE` | `DONT_APPLY_RECONCILE_TRACKER` | `UPDATE_STATUS` |
| 67 | `bde_series_api` | `PARTIAL` | `PARTIAL` | `MATCH` | `PARTIAL` | `NOT_NEEDED` | `KEEP_STATUS` |
| 68 | `aemet_opendata_series` | `PARTIAL` | `PARTIAL` | `MATCH` | `PARTIAL` | `NOT_NEEDED` | `KEEP_STATUS` |

## Notes

- Only one status transition is proposed: line `66` (`eurostat_sdmx`) from `PARTIAL` to `DONE`.
- PLACSP rows (`56`, `64`) remain `PARTIAL` and align with T23 recommendation to use temporary waivers while tracker policy reconciliation is approved.
- For every row, blocker-note text and next command are provided in:
  - `docs/etl/sprints/AI-OPS-10/exports/tracker_row_patch_plan.tsv`

Projected gate effect:
- mismatches now: `3`
- mismatches after row patch only: `2`
- mismatches after row patch + proposed waivers: `0`

## Direct evidence coverage check

For each proposed row, evidence bundle includes direct command/SQL artifacts:
- strict `*_run_snapshot.csv` (command result evidence)
- replay `*_run_snapshot.csv` when available (parity context)
- `docs/etl/sprints/AI-OPS-10/evidence/status-postrun.json` (postrun sql/tracker state)

Coverage result:
- rows missing direct command/SQL evidence: `0`

## Escalation rule check

T25 escalation condition:
- escalate if any row recommendation lacks direct command/SQL evidence.

Observed:
- all `7` row recommendations include direct command/SQL evidence paths.

Decision:
- `NO_ESCALATION`.
