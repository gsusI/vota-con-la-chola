# Senado Unlinked Skip-Blocked 17 Summary (2026-02-20)

Run ID:
- `senado_unlinked_skip_blocked17_20260220T142756Z`

Mode:
- Very wide skip-blocked sweep (`--include-unlinked`, no `--retry-forbidden`, `--limit-initiatives 4000`).

Outcome:
- `loop_1`: `ok=3`, `urls_to_fetch=3`, `skipped_forbidden=3051`
- `loop_2`: `ok=0`, `urls_to_fetch=0` (slice exhausted)
- Tranche delta: `+3` docs.

Key learning:
- At this stage, the remaining queue is dominated by already-blocked URLs; only very small fetchable pockets remain.
