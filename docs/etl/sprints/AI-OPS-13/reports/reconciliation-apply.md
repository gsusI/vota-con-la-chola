# AI-OPS-13 T4 Reconciliation Apply

Date:
- `2026-02-17`

Objective:
- Apply only policy-aligned tracker updates from Task 3/Task 4 execution evidence: transition to `DONE` only when strict-network evidence shows `exit_code=0` and `records_loaded>0` on real network.

## Inputs used

- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-13/exports/unblock_feasibility_matrix.csv`
- `docs/etl/sprints/AI-OPS-13/evidence/unblock-execution.log`
- `docs/etl/sprints/AI-OPS-13/evidence/bdns-api-discovery.log`
- `docs/etl/sprints/AI-OPS-13/evidence/aemet-contract-probe.log`
- `docs/etl/sprints/AI-OPS-13/evidence/baseline-gate.log`
- `docs/etl/mismatch-waivers.json`

## Applied updates

Edited tracker rows:
- line `57` (`bdns_autonomico`): status changed `PARTIAL -> DONE` with strict-network success evidence (`run_id=257`, `run_status=ok`, `run_records_loaded=50`, network URL `/bdnstrans/api/convocatorias/busqueda`).
- line `65` (`bdns_api_subvenciones`): status changed `PARTIAL -> DONE` with strict-network success evidence (`run_id=256`, `run_status=ok`, `run_records_loaded=50`, network URL `/bdnstrans/api/convocatorias/ultimas`).
- line `68` (`aemet_opendata_series`): kept `PARTIAL`, refreshed blocker to latest strict error (`run_id=258`, `aemet_blocker=contract`, JSON invalido con payload vacío).

Status transitions applied:
- `bdns_autonomico`: `PARTIAL -> DONE`
- `bdns_api_subvenciones`: `PARTIAL -> DONE`

Status transitions not applied:
- `aemet_opendata_series`: remains `PARTIAL` (no strict-network success evidence).
- `parlamento_galicia_deputados`, `parlamento_navarra_parlamentarios_forales`, `bde_series_api`: no status change in this task.

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
- `docs/etl/sprints/AI-OPS-13/evidence/tracker-status-postreconcile.log`
- `docs/etl/sprints/AI-OPS-13/evidence/tracker-gate-postreconcile.log`
- `docs/etl/sprints/AI-OPS-13/evidence/tracker-gate-postreconcile.exit`

Metrics delta:
- pre-apply baseline (`baseline-gate.log`): `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`, strict gate exit `0`.
- post-apply (`tracker-gate-postreconcile.log` / `.exit`): `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`, strict gate exit `0`.
- in-scope blocker set: `6 -> 4` remaining `PARTIAL` (two BDNS sources moved to `DONE`).

## Outcome

- Reconciliation apply followed policy: only strict-network-success sources were promoted.
- Tracker and SQL are aligned after apply (`mismatches=0`).
- Strict gate remains green (`exit 0`).

## Escalation rule check

T4 escalation condition:
- escalate if any status transition is applied without direct strict-network success evidence.

Observed:
- both applied transitions (`bdns_api_subvenciones`, `bdns_autonomico`) have direct strict-network success evidence in `unblock-execution.log`.

Decision:
- `NO_ESCALATION`.
