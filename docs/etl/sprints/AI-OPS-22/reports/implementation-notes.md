# AI-OPS-22 Implementation Notes

Date: 2026-02-17  
Owner: L2 Specialist Builder

## What Changed (Code)
- Added `view=alignment` to citizen app:
  - UI: `ui/citizen/index.html`
  - View selector: `Vista: alineamiento`
- Implemented local-first preferences:
  - localStorage key: `vclc_citizen_prefs_v1`
  - values: `topic_id -> support|oppose`
- Implemented opt-in share link via URL fragment:
  - `#prefs=v1:<payload>` where payload is compact `topic_id=<s|o>` CSV
  - preferences are never auto-written to query params

## Alignment Logic (Conservative)
- Comparable only when party stance is clear:
  - `support|oppose`
- Always unknown for:
  - `mixed|unclear|no_signal`
- Per party summary:
  - `match`, `mismatch`, `unknown`, `coverage`, and transparent `net` (`match-mismatch`)
- Drill-down:
  - per-party focus view lists each preference topic with:
    - user pref chip
    - party stance chip
    - result tag (`match|mismatch|unknown`)
    - audit links (`Temas`, `SQL`)

## Notes / Limitations
- Preferences are local to the browser unless the user explicitly generates a share link.
- Share links include preferences only in the fragment; opening the link will store prefs locally for convenience.
- No new ETL artifacts are required; alignment runs purely on the already-built citizen snapshot JSON.

