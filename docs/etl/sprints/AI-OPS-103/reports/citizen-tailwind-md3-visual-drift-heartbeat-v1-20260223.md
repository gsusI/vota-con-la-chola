# Citizen Tailwind+MD3 Visual Drift Heartbeat v1 (AI-OPS-103)

Date:
- 2026-02-23

Goal:
- Add an append-only trend lane for Tailwind+MD3 source/published drift and enforce strict parity in a last-N operational window.

What shipped:
- New heartbeat reporter:
  - `scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat.py`
  - reads drift digest and appends deduplicated heartbeat rows to:
    - `docs/etl/runs/citizen_tailwind_md3_visual_drift_digest_heartbeat.jsonl`
  - carries parity signals for:
    - `tokens`, `data tokens`, `generated css`, `ui html`
    - marker parity (`source/published/contract snapshot`)
- New heartbeat window reporter:
  - `scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_window.py`
  - strict last-N checks for:
    - `failed/degraded` rows
    - aggregate parity mismatches
    - per-asset mismatches (`tokens`, `data tokens`, `css`, `ui html`, markers)
    - latest-run parity safety (`latest_source_published_parity_ok`, `latest_marker_parity_ok`)
- New tests:
  - `tests/test_report_citizen_tailwind_md3_visual_drift_digest_heartbeat.py`
  - `tests/test_report_citizen_tailwind_md3_visual_drift_digest_heartbeat_window.py`
- `just` wiring:
  - new vars: `citizen_tailwind_md3_drift_heartbeat_*`
  - new lanes:
    - `just citizen-report-tailwind-md3-drift-heartbeat`
    - `just citizen-check-tailwind-md3-drift-heartbeat`
    - `just citizen-report-tailwind-md3-drift-heartbeat-window`
    - `just citizen-check-tailwind-md3-drift-heartbeat-window`
  - `just citizen-test-tailwind-md3` now includes heartbeat + window tests.

Validation:
- `just citizen-test-tailwind-md3`
- `just citizen-check-tailwind-md3-drift-digest`
- `just citizen-check-tailwind-md3-drift-heartbeat`
- `just citizen-check-tailwind-md3-drift-heartbeat-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict run result (20260223T152916Z):
- Drift digest: `status=ok`, `strict_fail_reasons=[]`
- Drift heartbeat: `status=ok`, `strict_fail_reasons=[]`
- Drift window: `status=ok`, `entries_in_window=1`, `parity_mismatch_in_window=0`
- Latest window parity checks:
  - `latest_source_published_parity_ok=true`
  - `latest_marker_parity_ok=true`

Evidence:
- `docs/etl/sprints/AI-OPS-103/evidence/citizen_tailwind_md3_visual_drift_digest_source_20260223T152916Z.json`
- `docs/etl/sprints/AI-OPS-103/evidence/citizen_tailwind_md3_visual_drift_digest_heartbeat_20260223T152916Z.json`
- `docs/etl/sprints/AI-OPS-103/evidence/citizen_tailwind_md3_visual_drift_digest_heartbeat_window_20260223T152916Z.json`
- `docs/etl/sprints/AI-OPS-103/evidence/just_citizen_test_tailwind_md3_20260223T152916Z.txt`
- `docs/etl/sprints/AI-OPS-103/evidence/just_citizen_check_tailwind_md3_drift_digest_20260223T152916Z.txt`
- `docs/etl/sprints/AI-OPS-103/evidence/just_citizen_check_tailwind_md3_drift_heartbeat_20260223T152916Z.txt`
- `docs/etl/sprints/AI-OPS-103/evidence/just_citizen_check_tailwind_md3_drift_heartbeat_window_20260223T152916Z.txt`
- `docs/etl/sprints/AI-OPS-103/evidence/just_citizen_release_regression_suite_20260223T152916Z.txt`
- `docs/etl/sprints/AI-OPS-103/evidence/just_explorer_gh_pages_build_20260223T152916Z.txt`
