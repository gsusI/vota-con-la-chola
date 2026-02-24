# Senado Drain Loop 3 Summary (2026-02-20)

Run ID:
- `senado_drain_loop3_20260220T123003Z`

Command mode:
- `backfill-initiative-documents` in bounded passes:
  - `--include-unlinked --retry-forbidden --limit-initiatives 40 --max-docs-per-initiative 1 --timeout 10`

Loop outcomes:
- `loop_1`: `ok=80`, `fail_entries=0`
- `loop_2`: `ok=20`, `fail_entries=30`
- `loop_3`: `ok=0`, `fail_entries=30` -> stop (throttle window)

Session delta:
- Senate docs downloaded in this tranche: `+100`

Post-run DB status:
- `senado_iniciativas` doc-link coverage: `3229/7905` (`40.85%`)
- Senate linked-to-votes initiatives with downloaded docs: `616/647` (`95.21%`)

Operational note:
- Upstream remains intermittent; bounded retries still produce incremental progress.
- Stop at first `fetched_ok=0` loop and resume later to avoid low-yield churn.
