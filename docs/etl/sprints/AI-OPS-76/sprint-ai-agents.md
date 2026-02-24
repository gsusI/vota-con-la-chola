# AI-OPS-76 Prompt Pack

Objective:
- Ship a mobile-first performance pass for `/citizen` with enforceable budgets and interaction-latency contract checks.

Acceptance gates:
- Improve mobile UX/perf in `ui/citizen/index.html` (touch targets, reduced motion, render cost controls).
- Add explicit interaction latency contract (`debounce` + coalesced compare render markers).
- Add machine-readable budget report for UI bundle + snapshot + interaction markers.
- Add strict tests/just targets for mobile contract and budget check.
- Publish sprint evidence and closeout.

Status update (2026-02-23):
- Implemented and validated with reproducible sprint evidence.
