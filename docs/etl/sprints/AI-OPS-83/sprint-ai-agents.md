# AI-OPS-83 Prompt Pack

Objective:
- Ship mobile observability v1 for `/citizen`: input-to-render latency sampling plus a strict percentile gate (`p50/p90`) with reproducible artifacts.

Acceptance gates:
- Add deterministic client-side sampling markers for key `/citizen` interactions and expose local export/summary hooks.
- Add a machine-readable observability contract report with `input_to_render_p50_ms`, `input_to_render_p90_ms`, `input_to_render_p95_ms`, and `sample_count`.
- Add strict pass/fail behavior with thresholds + minimum sample contract.
- Wire `just` targets for test/report/check and include this lane in the citizen release regression suite.
- Keep existing mobile-performance contract green after instrumentation changes.
- Publish sprint artifacts under `docs/etl/sprints/AI-OPS-83/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence.
