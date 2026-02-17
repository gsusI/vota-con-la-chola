# AI-OPS-10 T22 Tracker Gate Postrun

Date:
- `2026-02-17`

Objective:
- Run tracker status and strict gate after recompute wave, capture logs, and summarize post-run gate metrics.

## Commands executed

1. Tracker status:

```bash
just etl-tracker-status > docs/etl/sprints/AI-OPS-10/evidence/tracker-status-postrun.log 2>&1
```

- exit code: `0`

2. Tracker strict gate:

```bash
just etl-tracker-gate > docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.log 2>&1
```

- exit code: `1`
- terminal failure line: `FAIL: checklist/sql mismatches detected.`

## Evidence files

- `docs/etl/sprints/AI-OPS-10/evidence/tracker-status-postrun.log`
- `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.log`
- `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-mismatch-sources.csv`

## Post-run summary metrics

`tracker-status-postrun.log`:
- `tracker_sources=35`
- `sources_in_db=42`
- `mismatches=3`
- `waived_mismatches=0`
- `waivers_active=0`
- `waivers_expired=0`
- `done_zero_real=0`

`tracker-gate-postrun.log`:
- `tracker_sources=35`
- `sources_in_db=42`
- `mismatches=3`
- `waived_mismatches=0`
- `waivers_active=0`
- `waivers_expired=0`
- `done_zero_real=0`

## Mismatch sources (strict gate)

From `docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-mismatch-sources.csv`:

- `eurostat_sdmx`: `checklist=PARTIAL`, `sql=DONE`, `max_net=2394`, `last_loaded=2`
- `placsp_autonomico`: `checklist=PARTIAL`, `sql=DONE`, `max_net=106`, `last_loaded=2`
- `placsp_sindicacion`: `checklist=PARTIAL`, `sql=DONE`, `max_net=106`, `last_loaded=3`

Delta vs kickoff baseline (`docs/etl/sprints/AI-OPS-10/kickoff.md`):
- `mismatches`: `0 -> 3`
- `waivers_expired`: `0 -> 0`
- `done_zero_real`: `0 -> 0`

## Coverage against source evidence

- `eurostat_sdmx` is covered by `docs/etl/sprints/AI-OPS-10/reports/eurostat-apply.md` (`strict-network` success with non-zero real load, replay non-zero).
- `placsp_autonomico` and `placsp_sindicacion` are covered by `docs/etl/sprints/AI-OPS-10/reports/placsp-replay-run.md` and `docs/etl/sprints/AI-OPS-10/reports/placsp-strict-run.md` (strict TLS failures plus successful from-file/replay evidence).

Interpretation:
- strict gate failed due checklist vs SQL status mismatch on three in-scope carryover sources.
- no `done_zero_real` regressions and no expired waivers were introduced.

## Escalation rule check

T22 escalation condition:
- escalate if strict gate fails with new mismatches not covered by source evidence.

Observed:
- strict gate failed (`exit=1`) with `mismatches=3`,
- mismatch set is entirely mapped to existing source evidence artifacts listed above.

Decision:
- `NO_ESCALATION`.
