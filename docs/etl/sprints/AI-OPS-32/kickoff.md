# AI-OPS-32 Kickoff

Date:
- 2026-02-22

Objective:
- Decouple declared-lane enforce runs from vote-gate dependency to prevent false blocking in declared-only operational loops.

Why now:
- AI-OPS-31 added declared gating, but operational declared checks still depended on vote gate state when using `--enforce-gate`.
- Need deterministic declared closeout commands that can run independently.

Primary lane (controllable):
- Add `--skip-vote-gate` to `quality-report`, wire declared `just` targets to use it by default, and validate with tests + real evidence.

Acceptance gates:
- CLI supports `--skip-vote-gate` and enforce semantics are correct.
- `parl-quality-report-declared*` targets use skip-vote-gate by default.
- Unit tests prove fail-without-skip and pass-with-skip behavior.
- Real `just parl-quality-report-declared-enforce` run passes and emits evidence.
