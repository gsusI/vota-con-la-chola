# AI-OPS-10 T23 Waiver Candidates

Date:
- `2026-02-17`

Objective:
- Generate deterministic waiver candidates from post-run mismatch evidence without mutating waiver policy files.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/evidence/tracker-status-postrun.log`
- `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.log`
- `docs/etl/mismatch-waivers.json`
- `scripts/e2e_tracker_status.py`

## Output contract artifacts

- `docs/etl/sprints/AI-OPS-10/exports/waiver_candidates_ai_ops_10.csv`
- `docs/etl/sprints/AI-OPS-10/reports/waiver-candidates.md`

## Candidate generation summary

Mismatch sources extracted from postrun logs:
- `eurostat_sdmx`
- `placsp_autonomico`
- `placsp_sindicacion`

Current waiver state (from `docs/etl/mismatch-waivers.json` as of `2026-02-17`):
- active waivers: `0`
- expired waivers: `0`

Recommendations produced in `waiver_candidates_ai_ops_10.csv`:
- `DONT_APPLY_RECONCILE_TRACKER`: `1` (`eurostat_sdmx`)
- `APPLY_TEMP_WAIVER`: `2` (`placsp_autonomico`, `placsp_sindicacion`)

Suggested temporary waiver expiry:
- `2026-02-24` for PLACSP mismatch rows (owner suggestion: `L2`)

## Apply / Don’t-Apply recommendation

Per-source recommendation:
1. `eurostat_sdmx`: `DONT_APPLY_RECONCILE_TRACKER`
2. `placsp_autonomico`: `APPLY_TEMP_WAIVER`
3. `placsp_sindicacion`: `APPLY_TEMP_WAIVER`

Overall:
- `APPLY_PARTIAL` (apply only to the two PLACSP rows; do not apply waiver to Eurostat).

Rationale:
- Eurostat has strict-network success and non-zero replay in AI-OPS-10 evidence; mismatch is tracker/sql state lag.
- PLACSP rows are intentionally tracked as blocked `PARTIAL` while SQL computes `DONE`, so a short waiver can keep strict gate deterministic pending row-level reconciliation.

## Escalation rule check

T23 escalation condition:
- escalate if candidate generation would silently mutate waiver policy files.

Observed:
- `docs/etl/mismatch-waivers.json` SHA256 before: `21ce68ff69276d43fae83bd4cb3e90bc1a1c20f02f9ee602928459e7ba70b4fe`
- `docs/etl/mismatch-waivers.json` SHA256 after: `21ce68ff69276d43fae83bd4cb3e90bc1a1c20f02f9ee602928459e7ba70b4fe`
- no edits were applied to waiver policy JSON.

Decision:
- `NO_ESCALATION`.
