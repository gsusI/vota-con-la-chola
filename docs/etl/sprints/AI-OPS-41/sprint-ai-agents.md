# AI-OPS-41 Prompt Pack

Objective:
- Promote citizen preset link behavior to a single fixture-driven contract across read and share roundtrips.

Acceptance gates:
- `tests/fixtures/citizen_preset_hash_matrix.json` migrates to schema `v2` with:
  - `hash_cases` (read path)
  - `share_cases` (share URL build + decode roundtrip)
- `tests/test_citizen_preset_codec.js` enforces both fixture sections.
- Build + tracker gates remain green.

Status update (2026-02-22):
- Fixture schema upgraded to `v2` with edge cases for repeated keys, `%2B`/`+` pack normalization, and whitespace trimming.
- Share contract now fixture-backed with deterministic hash assertions and decoded roundtrip checks.
- Tests refactored to use fixture-only loops for both read and share behavior.
- evidence:
  - `docs/etl/sprints/AI-OPS-41/evidence/citizen_preset_codec_tests_20260222T210125Z.txt`
  - `docs/etl/sprints/AI-OPS-41/evidence/citizen_preset_fixture_markers_20260222T210125Z.txt`
  - `docs/etl/sprints/AI-OPS-41/evidence/explorer_gh_pages_build_20260222T210125Z.txt`
  - `docs/etl/sprints/AI-OPS-41/evidence/tracker_gate_postdocs_20260222T210125Z.txt`
