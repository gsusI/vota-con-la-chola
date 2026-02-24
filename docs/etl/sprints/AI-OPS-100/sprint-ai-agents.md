# AI-OPS-100 Prompt Pack

Objective:
- Ship concern-pack outcomes heartbeat v1 so `/citizen` concern-pack health has append-only trend coverage and strict last-N threshold checks.

Acceptance gates:
- Add concern-pack outcomes heartbeat reporter (`scripts/report_citizen_concern_pack_outcomes_heartbeat.py`).
- Add concern-pack outcomes heartbeat window reporter (`scripts/report_citizen_concern_pack_outcomes_heartbeat_window.py`).
- Track threshold-violation counts/rates for weak-pack followthrough and unknown-pack-select-share.
- Add deterministic tests for heartbeat and window strict behavior.
- Wire new `just` report/check/test lanes and include concern-pack outcomes heartbeat tests in `citizen-release-regression-suite`.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`heartbeat_status=ok`, `window_status=ok`, `weak_pack_followthrough_violations_in_window=0`, `unknown_pack_select_share_violations_in_window=0`).
