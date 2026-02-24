# Citizen Preset Roundtrip Fixtures (AI-OPS-41)

Date:
- 2026-02-22

Goal:
- Make citizen preset behavior extension-safe by expressing both read and share-link roundtrip expectations in one fixture contract.

## What shipped

1. Fixture schema v2
- `tests/fixtures/citizen_preset_hash_matrix.json` now defines:
  - `hash_cases`
  - `share_cases`
- Added normalization edge rows:
  - repeated keys (`method`, `concerns`)
  - `%2B` / `+` handling in `pack`
  - value whitespace trimming

2. Fixture-driven share roundtrip tests
- `tests/test_citizen_preset_codec.js` now validates `buildAlignmentPresetShareUrl` with fixture rows.
- Assertions now include:
  - stripped query (`search`)
  - deterministic `hash`
  - decoded preset parity via `readPresetFromHash`

3. Collaboration payoff
- New edge cases are now added by editing fixture rows only.
- Human QA and subagents can validate contract changes without rewriting JS assertions.

## Validation evidence

- Codec tests:
  - `docs/etl/sprints/AI-OPS-41/evidence/citizen_preset_codec_tests_20260222T210125Z.txt`
- Fixture markers:
  - `docs/etl/sprints/AI-OPS-41/evidence/citizen_preset_fixture_markers_20260222T210125Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-41/evidence/explorer_gh_pages_build_20260222T210125Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-41/evidence/tracker_gate_postdocs_20260222T210125Z.txt`

Outcome:
- Preset contract is now fixture-native for both decode and share paths, reducing drift risk as link semantics evolve.
