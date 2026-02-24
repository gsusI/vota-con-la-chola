# Senado Unlinked Skip-Blocked 16 Summary (2026-02-20)

Run ID:
- `senado_unlinked_skip_blocked16_20260220T142634Z`

Mode:
- Wide skip-blocked sweep (`--include-unlinked`, no `--retry-forbidden`, `--limit-initiatives 2000`).

Outcome:
- `loop_1`: `ok=1`, `urls_to_fetch=54`, `skipped_forbidden=2583`
- `loop_2`: `ok=11`, `urls_to_fetch=35`
- `loop_3`: `ok=24`, `urls_to_fetch=24`
- `loop_4`: `ok=0`, `urls_to_fetch=0` (slice exhausted)
- Tranche delta: `+36` docs.

Key learning:
- For the non-linked tail, skip-blocked mode can still recover small pockets of fetchable URLs when wide initiative windows are used.
