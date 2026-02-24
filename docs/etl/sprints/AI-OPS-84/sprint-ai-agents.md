# AI-OPS-84 Prompt Pack

Objective:
- Ship a build-time Tailwind+MD3 UI-system slice for `/citizen` with deterministic token->CSS generation, strict contract checks, and release parity integration.

Acceptance gates:
- Add MD3 token source of truth + deterministic generated CSS artifact under `ui/citizen/`.
- Wire generated CSS into `/citizen` and keep UI/server/GH Pages routes aligned.
- Add strict machine-readable Tailwind+MD3 contract (`ok|failed`) with budget + marker checks.
- Add tests + `just` wrappers for build/sync/report/check and include lane in release regression suite.
- Keep release-hardening strict checks green after GH Pages build.
- Publish sprint artifacts under `docs/etl/sprints/AI-OPS-84/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence.
