# AI-OPS-37 Prompt Pack

Objective:
- Harden citizen concerns configuration by enforcing a deterministic `concerns_v1` contract in code, tests, and build.

Acceptance gates:
- Validator script exists and enforces:
  - root contract (`version`, `concerns`, `packs`)
  - concern contract (`id`, `label`, `description`, `keywords`)
  - pack contract (`id`, `label`, `concern_ids`, `tradeoff`)
  - referential integrity (`pack.concern_ids` -> known concern ids) and full pack coverage.
- Unit tests cover pass/fail scenarios and current repo config.
- `explorer-gh-pages-build` executes validator and remains green on current data.
- Tracker gate remains green.

Status update (2026-02-22):
- `scripts/validate_citizen_concerns.py` added:
  - structured JSON report (`valid`, counts, `errors`, `warnings`)
  - strict checks for concern/pack schema and referential integrity
  - CLI with `--path`, `--out`, `--max-issues`
- `tests/test_validate_citizen_concerns.py` added:
  - valid minimal config pass
  - contract error detection (duplicate ids, unknown concern refs, missing required fields)
  - repository config validity check (`ui/citizen/concerns_v1.json`)
- `justfile` updated:
  - `explorer-gh-pages-build` now runs `python3 scripts/validate_citizen_concerns.py --path docs/gh-pages/citizen/data/concerns_v1.json`
- evidence:
  - `docs/etl/sprints/AI-OPS-37/evidence/citizen_concerns_validate_20260222T202800Z.json`
  - `docs/etl/sprints/AI-OPS-37/evidence/validate_citizen_concerns_tests_20260222T202804Z.txt`
  - `docs/etl/sprints/AI-OPS-37/evidence/explorer_gh_pages_build_20260222T202659Z.txt`
  - `docs/etl/sprints/AI-OPS-37/evidence/tracker_gate_20260222T202727Z.txt`
