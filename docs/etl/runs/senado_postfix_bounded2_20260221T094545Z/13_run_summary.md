# Senado Initiative Docs - Secondary Wide Pass (2026-02-21)

## Goal
Probe additional document links after the primary queue-fix drain.

## Command Pattern
`backfill-initiative-documents --include-unlinked --retry-forbidden --limit-initiatives 350 --max-docs-per-initiative 2`

## Result
- Start: `7248/8229`
- End: `7248/8229`
- Delta: `0`

## Notes
- This pass expanded known link rows but yielded no additional successful downloads in the sampled window.
- Remaining queue in this slice was dominated by hard 403/500/404 behavior.
