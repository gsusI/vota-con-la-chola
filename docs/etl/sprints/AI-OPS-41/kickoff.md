# AI-OPS-41 Kickoff

Date:
- 2026-02-22

Objective:
- Extend citizen preset fixture coverage to roundtrip URL fragment normalization edge cases and keep fixtures as the only contract extension point.

Why now:
- AI-OPS-40 established a canonical hash matrix for read-side behavior.
- Share-link generation (`buildAlignmentPresetShareUrl`) still relied on ad-hoc test assertions instead of fixture rows.

Primary lane (controllable):
- Upgrade fixture schema to include `hash_cases` + `share_cases`, then enforce both in `tests/test_citizen_preset_codec.js`.

Acceptance gates:
- Fixture v2 covers repeated keys, whitespace normalization, and share-link roundtrip rows.
- Tests iterate both `hash_cases` and `share_cases` and assert deterministic hash/decoded outcomes.
- `just citizen-test-preset-codec`, `just explorer-gh-pages-build`, and `just etl-tracker-gate` pass with evidence.
