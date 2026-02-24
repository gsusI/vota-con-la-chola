# AI-OPS-101 Prompt Pack

Objective:
- Ship trust-action nudges outcomes heartbeat v1 so `/citizen` trust-action telemetry has append-only trend coverage and strict last-N clickthrough threshold checks.

Acceptance gates:
- Add trust-action nudges heartbeat reporter (`scripts/report_citizen_trust_action_nudges_heartbeat.py`).
- Add trust-action nudges heartbeat window reporter (`scripts/report_citizen_trust_action_nudges_heartbeat_window.py`).
- Track threshold-violation counts/rates for nudge clickthrough minimum compliance.
- Add deterministic tests for heartbeat and window strict behavior.
- Wire new `just` report/check/test lanes and include trust-action nudges heartbeat tests in `citizen-release-regression-suite`.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`heartbeat_status=ok`, `window_status=ok`, `nudge_clickthrough_violations_in_window=0`, `latest_thresholds_ok=true`).
