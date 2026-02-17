# GH Pages Integration (Citizen App)

Sprint: `AI-OPS-17`  
Date: `2026-02-17`

## Where We Are Now
- Citizen UI (static): `ui/citizen/index.html`
- Exporter (deterministic snapshot): `scripts/export_citizen_snapshot.py`
- Concerns config (keyword tags, navigational only): `ui/citizen/concerns_v1.json`
- GH Pages build existed, but did not ship the citizen app.

## What Changed
- `justfile:explorer-gh-pages-build` now:
  - creates `docs/gh-pages/citizen/` and `docs/gh-pages/citizen/data/`
  - copies `ui/citizen/index.html` to `docs/gh-pages/citizen/index.html`
  - copies `ui/citizen/concerns_v1.json` to `docs/gh-pages/citizen/data/concerns_v1.json`
  - exports `docs/gh-pages/citizen/data/citizen.json` from the configured DB (`topic_set_id=1`, `computed_method=auto`, size guard `<= 5MB`)
- `ui/graph/explorers.html` adds a visible entry-point card linking to `/citizen`.

## How To Build (Reproducible)
```bash
DB_PATH=etl/data/staging/politicos-es.db SNAPSHOT_DATE=2026-02-12 just explorer-gh-pages-build
```

## Acceptance Checks (PASS/FAIL)
```bash
test -f docs/gh-pages/citizen/index.html
test -f docs/gh-pages/citizen/data/concerns_v1.json
test -f docs/gh-pages/citizen/data/citizen.json
rg -n "citizen/" docs/gh-pages/index.html
```

## Notes / Constraints
- Static-only: the citizen app fetches local files (`./data/citizen.json`, `./data/concerns_v1.json`).
- If the export grows beyond bounds, the build must fail (via `--max-bytes`).

## What’s Next
- Add `scripts/validate_citizen_snapshot.py` + KPIs and wire it into the build gate (AI-OPS-17 Task 7).
