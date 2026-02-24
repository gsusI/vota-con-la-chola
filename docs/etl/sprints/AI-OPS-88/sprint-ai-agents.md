# AI-OPS-88 Prompt Pack

Objective:
- Ship release-trace digest v1: a single machine-readable JSON card that summarizes the latest release-hardening run and enforces freshness SLA.

Acceptance gates:
- Add reporter `scripts/report_citizen_release_trace_digest.js` with status contract `ok|degraded|failed`.
- Read latest release-hardening artifact and expose key release metrics in a compact JSON envelope.
- Enforce strict modes: `--strict` (fail on `failed`) and `--strict-require-complete` (fail on non-`ok`).
- Add dedicated test lane and include it in `citizen-release-regression-suite`.
- Add `just` wrappers for report/check flows with deterministic output path in sprint evidence.
- Keep release hardening and GH Pages build green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`status=ok`, `contract_complete=true`).
