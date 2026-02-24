# AI-OPS-40 Prompt Pack

Objective:
- Convert citizen preset hash behavior into a fixture-driven contract that is easy for humans and agents to review, extend, and gate.

Acceptance gates:
- Create `tests/fixtures/citizen_preset_hash_matrix.json` with explicit good/bad hash examples.
- `tests/test_citizen_preset_codec.js` iterates that matrix and enforces deterministic outcomes.
- Preserve existing roundtrip/share-url coverage.
- Build + tracker gates remain green.

Status update (2026-02-22):
- Added canonical fixture matrix with seven cases (non-preset hash, valid minimal hash, valid rich hash, unknown version, malformed encoding, empty payload, unsupported fields only).
- Refactored codec tests to consume the matrix and assert contract fields per case.
- Preserved existing encode/decode normalization + share URL tests.
- evidence:
  - `docs/etl/sprints/AI-OPS-40/evidence/citizen_preset_codec_tests_20260222T205440Z.txt`
  - `docs/etl/sprints/AI-OPS-40/evidence/citizen_preset_fixture_markers_20260222T205440Z.txt`
  - `docs/etl/sprints/AI-OPS-40/evidence/explorer_gh_pages_build_20260222T205440Z.txt`
  - `docs/etl/sprints/AI-OPS-40/evidence/tracker_gate_postdocs_20260222T205723Z.txt`
