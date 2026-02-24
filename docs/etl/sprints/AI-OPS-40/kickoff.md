# AI-OPS-40 Kickoff

Date:
- 2026-02-22

Objective:
- Publish a deterministic preset-hash fixture matrix (valid + invalid examples) and enforce it in codec tests so collaborators can extend the contract without guessing.

Why now:
- AI-OPS-39 hardened malformed-hash semantics (`error_code`) but examples were still spread across ad-hoc tests.
- We need one explicit artifact that doubles as QA checklist and test source of truth.

Primary lane (controllable):
- Add `tests/fixtures/citizen_preset_hash_matrix.json` and consume it from `tests/test_citizen_preset_codec.js`.

Acceptance gates:
- Fixture matrix includes both success and failure cases for `#preset` hashes.
- Node tests load matrix rows and validate `preset`/`error_code`/`error` behavior per case.
- `just citizen-test-preset-codec`, `just explorer-gh-pages-build`, and `just etl-tracker-gate` pass with evidence.
