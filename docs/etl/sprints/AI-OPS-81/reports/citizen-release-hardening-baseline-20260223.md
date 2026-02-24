# Citizen Release Hardening Baseline (AI-OPS-81)

Date:
- 2026-02-23

Goal:
- Make `/citizen` release readiness deterministic and auditable with one strict checklist and one bundled regression lane.

What shipped:
- New machine-readable release checklist:
  - `scripts/report_citizen_release_hardening.js`
  - checks:
    - source/published parity for core assets (`index.html`, `preset_codec.js`, `onboarding_funnel.js`, `first_answer_accelerator.js`, `unknown_explainability.js`, `evidence_trust_panel.js`)
    - published snapshot budget + shape contract (`meta.as_of_date`, `meta.quality`, `topics`, `parties`, `party_topic_positions`)
    - concerns config shape contract (`concerns`, `packs`)
  - strict mode (`--strict`) exits non-zero when release is not ready.
- New strict tests:
  - `tests/test_report_citizen_release_hardening.js`
  - verifies strict pass on aligned assets and strict fail on parity drift.
- New `just` lanes:
  - `just citizen-test-release-hardening`
  - `just citizen-report-release-hardening`
  - `just citizen-check-release-hardening`
  - `just citizen-release-regression-suite` (preset/accessibility/trust/mobile/first-answer/unknown/pack-quality)

Validation:
- `node --test tests/test_report_citizen_release_hardening.js`
- `just citizen-test-release-hardening`
- `just citizen-release-regression-suite`
- `just citizen-report-release-hardening`
- `just explorer-gh-pages-build`
- `just citizen-check-release-hardening`

Readiness transition (evidence-first):
- Before build (`report` on stale published artifacts): `release_ready=false`, `total_fail=7`
- After build + strict check: `release_ready=true`, `total_fail=0`, `parity_ok_assets=6/6`

Evidence:
- `docs/etl/sprints/AI-OPS-81/evidence/citizen_release_hardening_contract_summary_20260223T131323Z.json`
- `docs/etl/sprints/AI-OPS-81/evidence/citizen_release_hardening_contract_markers_20260223T131323Z.txt`
- `docs/etl/sprints/AI-OPS-81/evidence/just_citizen_release_regression_suite_20260223T130301Z.txt`
- `docs/etl/sprints/AI-OPS-81/evidence/just_explorer_gh_pages_build_20260223T130812Z.txt`
- `docs/etl/sprints/AI-OPS-81/evidence/just_citizen_check_release_hardening_20260223T131323Z.txt`
