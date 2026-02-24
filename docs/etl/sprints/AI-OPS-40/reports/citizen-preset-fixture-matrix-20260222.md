# Citizen Preset Fixture Matrix (AI-OPS-40)

Date:
- 2026-02-22

Goal:
- Make malformed/valid `#preset` behavior auditable through one fixture artifact that powers both QA review and automated tests.

## What shipped

1. Canonical fixture matrix
- Added `tests/fixtures/citizen_preset_hash_matrix.json`.
- Contract fields per case:
  - `id`
  - `hash`
  - `expect.preset`
  - `expect.error_code`
  - `expect.error` or `expect.error_contains`

2. Fixture-driven tests
- `tests/test_citizen_preset_codec.js` now loads and iterates the matrix.
- Assertions are case-scoped and enforce deterministic outcomes for each hash example.
- Existing behavioral tests stay in place for encode/decode normalization and share-URL generation.

3. Collaboration value
- The fixture file is now the fastest path for adding new edge cases without rewriting test logic.
- Humans/subagents can review hash examples directly without reading JS implementation details.

## Validation evidence

- Codec tests:
  - `docs/etl/sprints/AI-OPS-40/evidence/citizen_preset_codec_tests_20260222T205440Z.txt`
- Fixture markers:
  - `docs/etl/sprints/AI-OPS-40/evidence/citizen_preset_fixture_markers_20260222T205440Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-40/evidence/explorer_gh_pages_build_20260222T205440Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-40/evidence/tracker_gate_postdocs_20260222T205723Z.txt`

Outcome:
- Preset hash behavior is now fixture-driven, discoverable, and safer to extend sprint-over-sprint.
