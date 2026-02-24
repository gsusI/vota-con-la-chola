# Citizen Tailwind+MD3 Visual Drift Digest v1 (AI-OPS-96)

Date:
- 2026-02-23

Goal:
- Add a strict, machine-readable drift digest that proves `/citizen` Tailwind+MD3 assets in source and published outputs remain synchronized.

What shipped:
- New drift digest reporter:
  - `scripts/report_citizen_tailwind_md3_visual_drift_digest.py`
  - checks source/published parity for:
    - tokens (`ui/citizen/tailwind_md3.tokens.json` vs `docs/gh-pages/citizen/tailwind_md3.tokens.json`)
    - published data tokens (`docs/gh-pages/citizen/data/tailwind_md3.tokens.json`)
    - CSS (`ui/citizen/tailwind_md3.generated.css` vs published)
    - UI HTML (`ui/citizen/index.html` vs published)
  - enforces marker snapshot parity for `md3-card`, `md3-chip`, `md3-button`, `md3-tab` across source/published/contract snapshot.
- New tests:
  - `tests/test_report_citizen_tailwind_md3_visual_drift_digest.py`
  - covers strict PASS (full parity) and strict FAIL (`css_parity_mismatch`).
- `just` wiring:
  - new vars for drift contract/published paths/output (`citizen_tailwind_md3_drift_*`)
  - new lanes:
    - `just citizen-report-tailwind-md3-drift-digest`
    - `just citizen-check-tailwind-md3-drift-digest`
  - `just citizen-test-tailwind-md3` now includes the new Python test.

Validation:
- `just citizen-test-tailwind-md3`
- `just citizen-check-tailwind-md3-drift-digest`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict run result:
- Tailwind contract: `status=ok`, `checks_all_ok=true`
- Drift digest: `status=ok`, `strict_fail_reasons=[]`
- Parity checks: tokens/data-tokens/CSS/UI-HTML all `true`
- Marker snapshots: source/published/contract all aligned (`md3-card=10`, `md3-chip=16`, `md3-button=28`, `md3-tab=9`)

Evidence:
- `docs/etl/sprints/AI-OPS-96/evidence/citizen_tailwind_md3_contract_latest.json`
- `docs/etl/sprints/AI-OPS-96/evidence/citizen_tailwind_md3_visual_drift_digest_latest.json`
- `docs/etl/sprints/AI-OPS-96/evidence/just_citizen_test_tailwind_md3_20260223T141344Z.txt`
- `docs/etl/sprints/AI-OPS-96/evidence/just_citizen_check_tailwind_md3_drift_digest_20260223T141344Z.txt`
- `docs/etl/sprints/AI-OPS-96/evidence/just_citizen_release_regression_suite_20260223T141344Z.txt`
- `docs/etl/sprints/AI-OPS-96/evidence/just_explorer_gh_pages_build_20260223T141344Z.txt`
