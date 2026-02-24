# Senado Infinite Retry Loop Checkpoint (2026-02-21)

Loop mode:
- Continuous retries with 60s cooldown:
  - skip-blocked wide pass (`--include-unlinked --limit-initiatives 4000`, no `--retry-forbidden`)
  - cookie retry pass (`--include-unlinked --retry-forbidden --limit-initiatives 60`)

Runtime:
- PID at launch: `19562`
- Log: `docs/etl/runs/senado_infinite_loop_20260221T081119Z/loop.log`

Purpose:
- Keep probing for transient reopen windows while the remaining Senate tail is in 403/500 plateau.
