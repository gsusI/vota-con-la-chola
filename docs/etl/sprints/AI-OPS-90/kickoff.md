# AI-OPS-90 Kickoff

Date:
- 2026-02-23

Primary objective:
- Land a mobile observability trend lane for `/citizen` so teams can monitor `p90` latency stability over time with one heartbeat stream and one strict last-N window report.

Definition of done:
- Heartbeat reporter exists and appends deduped entries in `docs/etl/runs/citizen_mobile_observability_heartbeat.jsonl`.
- Window reporter exists and emits strict checks for `failed/degraded` plus `p90` threshold violations.
- Reporter tests exist and pass.
- `just` wrappers exist for `test/report/check` for heartbeat and window.
- `citizen-release-regression-suite` includes the new heartbeat test lane.
- Sprint evidence/docs are published under `docs/etl/sprints/AI-OPS-90/`.
