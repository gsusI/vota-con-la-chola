# AI-OPS-21 Build Integration

Date: 2026-02-17  
Sprint: `AI-OPS-21`

## Decision
No ETL/export/build changes required.

Rationale:
- `just explorer-gh-pages-build` already exports and validates:
  - `docs/gh-pages/citizen/data/citizen.json` (combined)
  - `docs/gh-pages/citizen/data/citizen_votes.json`
  - `docs/gh-pages/citizen/data/citizen_declared.json`
- Coherence view is implemented as a UI-only lazy join of votes+declared artifacts.

## Contract
- Citizen UI must load method datasets from `./data/` paths (relative) so GH Pages works.
- Budgets remain enforced by existing validator runs in the build.

