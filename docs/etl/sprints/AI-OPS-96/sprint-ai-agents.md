# AI-OPS-96 Prompt Pack

Objective:
- Ship Tailwind+MD3 visual drift digest v1 so `/citizen` keeps strict source/published parity guarantees for tokens, CSS, HTML, and component marker snapshots.

Acceptance gates:
- Add a strict visual drift digest script for Tailwind+MD3 (`scripts/report_citizen_tailwind_md3_visual_drift_digest.py`).
- Validate parity for source vs published tokens/CSS/UI HTML and for published data tokens.
- Validate marker-count parity (`md3-card`, `md3-chip`, `md3-button`, `md3-tab`) across source/published and against the Tailwind contract snapshot.
- Add deterministic tests for pass/fail strict behavior in the new digest reporter.
- Wire `just` report/check lanes and include the new Python test in `just citizen-test-tailwind-md3`.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`status=ok`, `strict_fail_reasons=[]`, source/published parity `true` for tokens/data tokens/css/ui_html, marker snapshots aligned `10/16/28/9`).
