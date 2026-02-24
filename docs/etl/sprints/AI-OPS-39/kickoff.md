# AI-OPS-39 Kickoff

Date:
- 2026-02-22

Objective:
- Harden malformed `#preset` handling so citizen alignment links fail safely with explicit, deterministic error semantics.

Why now:
- AI-OPS-38 moved preset logic into a shared codec, but malformed hashes still lacked an explicit error-code contract.
- We need predictable behavior for bad/truncated links and avoid false "preset loaded" states.

Primary lane (controllable):
- Add preset error codes in codec, surface actionable hints in citizen UI, and cover malformed-hash cases with tests.

Acceptance gates:
- `ui/citizen/preset_codec.js` emits stable `error_code` for malformed/unsupported/empty/no-supported-fields hashes.
- Hashes with no valid preset fields are rejected (not treated as loaded preset).
- Citizen UI surfaces user-facing hints from `error_code`.
- `just citizen-test-preset-codec`, `just explorer-gh-pages-build`, and `just etl-tracker-gate` pass with evidence.
