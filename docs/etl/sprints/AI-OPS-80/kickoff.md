# AI-OPS-80 Kickoff

Date:
- 2026-02-23

Primary objective:
- Improve accessibility and readability in `/citizen` with low-risk static-first changes and machine-checkable UI contracts.

Scope:
- `ui/citizen/index.html`
- `tests/test_citizen_accessibility_readability_ui_contract.js`
- `justfile` (`citizen-test-accessibility-readability`)

Out-of-scope:
- data model or ETL changes
- backend API/runtime dependencies
- visual redesign or component-system migration

Definition of done:
- Keyboard skip-link + main focus landmark are present.
- Live-region and section/search/result aria markers are present.
- New accessibility/readability UI contract test passes via direct `node --test` and `just` target.
- Existing citizen regression lanes stay green.
- Sprint evidence + closeout are published in `docs/etl/sprints/AI-OPS-80/`.
