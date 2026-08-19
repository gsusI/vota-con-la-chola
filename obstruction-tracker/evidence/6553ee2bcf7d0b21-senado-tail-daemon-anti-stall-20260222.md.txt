# Senado Tail Daemon Anti-Stall Update (2026-02-22)

## Objective
Avoid infinite tail loops when Senate initiative-doc retries have no new lever.

## Change
Updated `scripts/senado_tail_daemon.sh` with explicit stop guards and a machine-readable stop artifact:

- new env knobs:
  - `MAX_IDLE_ROUNDS` (default `6`)
  - `MAX_ROUNDS` (default `0`, unlimited)
  - `STOP_ON_UNIFORM_404` (default `1`)
- new runtime counters per round:
  - `missing`, `m404`, `m403`, `m500`, `idle_rounds`
- stop reasons:
  - `complete`
  - `uniform_404_tail`
  - `no_progress`
  - `max_rounds`
- new artifact:
  - `RUN_DIR/_stop_summary.json`

## Smoke validation
- Run 1 (pre-check-order tweak):
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_tail_daemon_smoke_20260222T103326Z/_stop_summary.json`
  - stop reason: `max_rounds` (`round=1`, `missing=119`, `missing_404=119`)
- Run 2 (final check order):
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_tail_daemon_smoke2_20260222T103342Z/_stop_summary.json`
  - stop reason: `uniform_404_tail` (`round=1`, `missing=119`, `missing_404=119`)

## Real-pass validation
- Full-limits daemon run (production settings) also exits cleanly on the same stop reason:
  - `docs/etl/sprints/AI-OPS-27/evidence/senado_tail_daemon_real_20260222T103548Z/_stop_summary.json`
  - stop reason: `uniform_404_tail` (`round=1`, `missing=119`, `missing_404=119`)

## Operational impact
- The daemon now exits cleanly when the tail is uniformly blocked (`404`) instead of spinning forever.
- This enforces sprint policy (`no_new_lever` => bounded retry) while keeping evidence append-only.
