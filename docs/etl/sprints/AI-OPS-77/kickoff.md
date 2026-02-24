# AI-OPS-77 Kickoff

Date:
- 2026-02-23

Primary objective:
- Improve shared-link reliability in `/citizen` by making `#preset` decode/recovery robust and user-remediable.

Scope:
- `ui/citizen/preset_codec.js`
- `ui/citizen/index.html`
- fixture/tests/just targets for preset recovery and canonicalization

Out-of-scope:
- ETL source expansion or schema changes
- New backend endpoints
- Changes to stance scoring semantics

Definition of done:
- Recovery paths are deterministic and covered by fixture-driven tests.
- Canonical hash normalization is applied in UI when needed.
- User-visible remediation actions exist for invalid/legacy presets.
- Preset and regression gates pass with evidence captured in sprint folder.
