# Senado Drain Loop 4 Summary (2026-02-20)

Run ID:
- `senado_drain_loop4_20260220T134620Z`

Command mode:
- `backfill-initiative-documents` in bounded passes:
  - `--include-unlinked --retry-forbidden --limit-initiatives 40 --max-docs-per-initiative 1 --timeout 10`

Loop outcomes (saved loops):
- `loop_1`: `ok=46`, `fail_entries=30`
- `loop_2`: `ok=80`, `fail_entries=0`
- `loop_3`: `ok=15`, `fail_entries=30`
- `loop_4`: `ok=1`, `fail_entries=30`
- `loop_5`: `ok=1`, `fail_entries=30`
- `loop_6`: `ok=1`, `fail_entries=30`
- `loop_7`: `ok=2`, `fail_entries=30`
- `loop_8`: empty/incomplete after manual stop (low-yield phase)

Session delta:
- Senate docs downloaded in this tranche: `+146`

Post-run DB status:
- `senado_iniciativas` doc-link coverage: `3375/7905` (`42.69%`)
- Senate linked-to-votes initiatives with downloaded docs: `644/647` (`99.54%`)

Operational note:
- This tranche reached near-complete linked-vote coverage.
- Remaining gaps are now concentrated in a small tail (`3/647` linked initiatives missing docs).
