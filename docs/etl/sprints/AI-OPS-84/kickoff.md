# AI-OPS-84 Kickoff

Date:
- 2026-02-23

Primary objective:
- Land the Tailwind+MD3 migration slice as a deterministic build artifact with strict contracts, without regressing release hardening.

Definition of done:
- `ui/citizen/tailwind_md3.tokens.json` is the design token source of truth.
- `ui/citizen/tailwind_md3.generated.css` is reproducibly generated and checked in sync.
- `/citizen` references the generated CSS and server/build pipelines publish it.
- Strict Tailwind+MD3 contract checks and release-hardening checks pass.
