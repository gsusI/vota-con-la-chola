# Senado Finish Fast Summary (2026-02-20)

Run ID:
- `senado_finish_fast_20260220T144046Z`

Strategy:
- Round-based fast loop:
  - skip-blocked wide pass (`--include-unlinked --limit-initiatives 4000`, no `--retry-forbidden`)
  - if no fetchable URLs, cookie retry probe (`--retry-forbidden --cookie-file ... --limit-initiatives 60`)

Outcome:
- Start: `4393/7905`
- End: `5720/7905`
- Net: `+1327` docs in one run family.

Notable behavior:
- Highly bursty throughput. Several rounds delivered `+100..+120`, then long zero-gain periods.
- Linked-vote objective remained complete (`647/647`) throughout.
