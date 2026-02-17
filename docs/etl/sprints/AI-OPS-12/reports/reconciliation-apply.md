# AI-OPS-12 T4 Reconciliation Apply

Date:
- `2026-02-17`

Objective:
- Apply only policy-aligned tracker updates from Task 3 (`KEEP_PARTIAL` for all in-scope sources) and re-check strict gate.

## Inputs used

- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-12/exports/source_decision_packet.csv`
- `docs/etl/sprints/AI-OPS-12/evidence/baseline-gate.log`
- `docs/etl/sprints/AI-OPS-12/evidence/blocker-probe-refresh.log`
- `docs/etl/mismatch-waivers.json`

## Applied updates

Edited tracker rows (status unchanged):
- line `45` (`parlamento_galicia_deputados`): kept `PARTIAL`, refreshed blocker/evidence with latest strict probe (`run_id=250`, HTTP 403).
- line `53` (`parlamento_navarra_parlamentarios_forales`): kept `PARTIAL`, refreshed blocker/evidence (`run_id=251`, HTTP 403).
- line `57` (`bdns_autonomico`): kept `PARTIAL`, refreshed blocker/evidence (`run_id=252`, anti-bot HTML payload signature).
- line `65` (`bdns_api_subvenciones`): kept `PARTIAL`, refreshed blocker/evidence (`run_id=253`, anti-bot HTML payload signature).
- line `67` (`bde_series_api`): kept `PARTIAL`, refreshed blocker/evidence (`run_id=254`, DNS `Errno 8`).
- line `68` (`aemet_opendata_series`): kept `PARTIAL`, refreshed blocker/evidence (`run_id=255`, `aemet_blocker=contract`, HTTP 404).

Status transitions applied:
- none (`status_action=KEEP_STATUS` for all decision rows).

Waiver policy file:
- unchanged (`docs/etl/mismatch-waivers.json` SHA256: `21ce68ff69276d43fae83bd4cb3e90bc1a1c20f02f9ee602928459e7ba70b4fe`).

## Post-apply checker runs

Commands:

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17
```

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --as-of-date 2026-02-17 \
  --fail-on-mismatch \
  --fail-on-done-zero-real
```

Artifacts:
- `docs/etl/sprints/AI-OPS-12/evidence/tracker-status-postreconcile.log`
- `docs/etl/sprints/AI-OPS-12/evidence/tracker-gate-postreconcile.log`

Metrics delta:
- pre-apply baseline (`baseline-gate.log`): `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`, strict gate exit `0`.
- post-apply (`tracker-gate-postreconcile.log`): `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`, strict gate exit `0`.

## Outcome

- Task 3 decision was applied exactly: all six sources remain `PARTIAL` with refreshed blocker evidence.
- Strict tracker gate remains green after reconciliation apply.
- No waiver mutation and no fake `DONE` transitions.

## Escalation rule check

T4 escalation condition:
- escalate if any status transition is applied without direct strict-network success evidence.

Observed:
- no status transitions were applied.

Decision:
- `NO_ESCALATION`.
