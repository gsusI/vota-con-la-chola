# Senado Initiative Docs - Playwright Follow-up (2026-02-21)

## Goal
Test browser-profile assisted retries on remaining blocked legacy links.

## Command Pattern
`backfill-initiative-documents --include-unlinked --retry-forbidden --playwright-user-data-dir <profile> --playwright-headless`

## Result
- Start: `7248/8272`
- End: `7248/8272`
- Delta: `0`

## Notes
- In this specific live slice no net persisted gains landed.
- Keep as fallback tactic for intermittent windows; do not treat as primary drain path.
