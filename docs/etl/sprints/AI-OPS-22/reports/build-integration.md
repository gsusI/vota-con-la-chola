# AI-OPS-22 Build Integration Notes

Date: 2026-02-17  
Owner: L2 Specialist Builder

## Invariants (Must Keep)
- Single build command for GH Pages output:
  - `just explorer-gh-pages-build`
- Citizen artifacts remain bounded and validated in the build.
- No server dependency for `/citizen`.

## Privacy Rule (Prefs)
`AGENTS.md` updated to include a privacy exception for citizen preferences:
- local-first (`localStorage`) by default
- never auto-write prefs to URL query params
- share link is opt-in and should use URL fragment (`#...`)

Reference:
- `AGENTS.md`

