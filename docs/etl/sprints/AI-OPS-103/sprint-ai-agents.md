# AI-OPS-103 Prompt Pack

Objective:
- Ship Tailwind+MD3 visual drift heartbeat v1 so `/citizen` keeps an append-only parity trend and strict last-N parity window checks for source/published assets.

Acceptance gates:
- Add visual-drift heartbeat reporter (`scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat.py`).
- Add visual-drift heartbeat-window reporter (`scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_window.py`).
- Enforce strict last-N parity checks for tokens/data/css/ui-html + marker parity on latest run.
- Add deterministic tests for heartbeat append/dedupe and window strict behavior.
- Wire new `just` report/check lanes and include heartbeat tests in `citizen-test-tailwind-md3`.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`heartbeat_status=ok`, `window_status=ok`, `parity_mismatch_in_window=0`, `latest_source_published_parity_ok=true`).
