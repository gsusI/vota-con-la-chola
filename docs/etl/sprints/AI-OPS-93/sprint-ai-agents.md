# AI-OPS-93 Prompt Pack

Objective:
- Ship release-trace freshness heartbeat v1 so `/citizen` release-trace digest status is tracked over time with strict stale-window guards.

Acceptance gates:
- Add append-only heartbeat reporter for release-trace digest (`scripts/report_citizen_release_trace_digest_heartbeat.py`).
- Add strict last-N heartbeat window reporter with stale/failed/degraded checks (`scripts/report_citizen_release_trace_digest_heartbeat_window.py`).
- Add deterministic tests for append/dedupe/strict behavior and window checks.
- Wire `just` report/check/test lanes and include the lane in `citizen-release-regression-suite`.
- Keep release regression suite and `explorer-gh-pages-build` green.
- Publish sprint evidence under `docs/etl/sprints/AI-OPS-93/evidence/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`heartbeat_status=ok`, `window_status=ok`, `stale_in_window=0`, `strict_fail_reasons=[]`).
