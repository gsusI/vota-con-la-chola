# AI-OPS-38 Kickoff

Date:
- 2026-02-22

Objective:
- Harden citizen alignment preset links by extracting `#preset=v1` codec logic into a reusable module with deterministic tests and static build parity.

Why now:
- The preset flow is now central to onboarding/shareability; regressions in hash encoding/decoding would silently break link reproducibility.
- Previous implementation lived inline in `index.html`, making focused tests harder and increasing drift risk.

Primary lane (controllable):
- Ship `ui/citizen/preset_codec.js`, wire citizen UI to it, expose local server route + GH Pages copy, and add roundtrip tests.

Acceptance gates:
- Citizen UI uses shared preset codec module for encode/decode/read/build.
- Node tests cover roundtrip normalization, invalid version handling, and share URL behavior.
- `just explorer-gh-pages-build` still passes and includes `docs/gh-pages/citizen/preset_codec.js`.
- `just etl-tracker-gate` remains green.
