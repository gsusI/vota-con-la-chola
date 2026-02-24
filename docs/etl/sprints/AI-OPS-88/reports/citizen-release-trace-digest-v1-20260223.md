# Citizen Release-Trace Digest v1 (AI-OPS-88)

Date:
- 2026-02-23

Goal:
- Publish one strict JSON digest that summarizes release hardening readiness and freshness, so product/release status can be consumed without reading full regression outputs.

What shipped:
- New reporter:
  - `scripts/report_citizen_release_trace_digest.js`
  - input: release-hardening JSON
  - output: compact digest with `status`, `checks`, `release_trace`, thresholds, and reason lists
  - strict modes:
    - `--strict`: exit non-zero on `failed`
    - `--strict-require-complete`: with strict, also fail on `degraded`
- New tests:
  - `tests/test_report_citizen_release_trace_digest.js`
  - pass/stale/fail scenarios covered
- New `just` lanes:
  - `just citizen-test-release-trace-digest`
  - `just citizen-report-release-trace-digest`
  - `just citizen-check-release-trace-digest`
  - lane included in `just citizen-release-regression-suite`

Validation:
- `just citizen-test-release-trace-digest`
- `just citizen-check-release-hardening`
- `just citizen-report-release-trace-digest`
- `just citizen-check-release-trace-digest`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict release-trace result:
- `status=ok`
- `release_total_checks=30`
- `release_total_fail=0`
- `release_ready=true`
- `parity_ok_assets=9`
- `parity_total_assets=9`
- `release_age_minutes=0.002`
- `contract_complete=true`

Evidence:
- `docs/etl/sprints/AI-OPS-88/evidence/citizen_release_trace_digest_latest.json`
- `docs/etl/sprints/AI-OPS-88/evidence/citizen_release_trace_digest_20260223T125445Z.json`
- `docs/etl/sprints/AI-OPS-88/evidence/citizen_release_trace_digest_summary_20260223T125445Z.json`
- `docs/etl/sprints/AI-OPS-88/evidence/just_citizen_test_release_trace_digest_20260223T125445Z.txt`
- `docs/etl/sprints/AI-OPS-88/evidence/just_citizen_check_release_hardening_20260223T125445Z.txt`
- `docs/etl/sprints/AI-OPS-88/evidence/just_citizen_report_release_trace_digest_20260223T125445Z.txt`
- `docs/etl/sprints/AI-OPS-88/evidence/just_citizen_check_release_trace_digest_20260223T125445Z.txt`
- `docs/etl/sprints/AI-OPS-88/evidence/just_citizen_release_regression_suite_20260223T125445Z.txt`
- `docs/etl/sprints/AI-OPS-88/evidence/just_explorer_gh_pages_build_20260223T125445Z.txt`
