# AI-OPS-88 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add a strict release-trace digest card so collaborators can poll one JSON file to know if the latest citizen release hardening run is fresh and complete.

Definition of done:
- `scripts/report_citizen_release_trace_digest.js` exists and reads release hardening JSON.
- Reporter emits `ok|degraded|failed` with explicit `checks`, `degraded_reasons`, and `failure_reasons`.
- `--strict` and `--strict-require-complete` modes are supported.
- Reporter tests exist and pass.
- `just` report/check/test lanes exist and release regression suite includes this lane.
- Sprint evidence and docs are published under `docs/etl/sprints/AI-OPS-88/`.
