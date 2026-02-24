# Citizen Explainability Outcomes Digest v1 (AI-OPS-92)

Date:
- 2026-02-23

Goal:
- Add measurable explainability adoption signals in `/citizen` and enforce a strict completeness gate for glossary/help-copy usage.

What shipped:
- Explainability outcomes telemetry instrumentation in `ui/citizen/index.html`:
  - local storage lane (`vclc_explainability_outcome_events_v1`)
  - event capture for:
    - `explainability_glossary_opened`
    - `explainability_glossary_term_interacted`
    - `explainability_help_copy_interacted`
  - debug APIs:
    - `__vclcExplainabilityOutcomeSummary`
    - `__vclcExplainabilityOutcomeExport`
    - `__vclcExplainabilityOutcomeClear`
- Machine-readable digest reporter:
  - `scripts/report_citizen_explainability_outcomes.py`
  - strict thresholds and `contract_complete` gate with:
    - glossary interaction minimum
    - help-copy interaction minimum
    - adoption sessions minimum
    - adoption completeness rate minimum
- Fixtures/tests:
  - `tests/fixtures/citizen_explainability_outcome_events_sample.jsonl`
  - `tests/test_citizen_explainability_outcomes_ui_contract.js`
  - `tests/test_report_citizen_explainability_outcomes.py`
- `just` lane wiring:
  - `citizen-test-explainability-outcomes`
  - `citizen-report-explainability-outcomes`
  - `citizen-check-explainability-outcomes`
  - `citizen-release-regression-suite` now includes the new explainability-outcomes lane

Validation:
- `just citizen-test-explainability-outcomes`
- `just citizen-report-explainability-outcomes`
- `just citizen-check-explainability-outcomes`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict digest result:
- `status=ok`
- `glossary_interaction_events_total=9` (threshold `8`)
- `help_copy_interaction_events_total=5` (threshold `5`)
- `adoption_sessions_total=6` (threshold `5`)
- `complete_adoption_sessions_total=4`
- `adoption_completeness_rate=0.666667` (threshold `0.6`)
- `contract_complete=true`

Evidence:
- `docs/etl/sprints/AI-OPS-92/evidence/citizen_explainability_outcomes_latest.json`
- `docs/etl/sprints/AI-OPS-92/evidence/citizen_explainability_outcomes_20260223T133324Z.json`
- `docs/etl/sprints/AI-OPS-92/evidence/citizen_explainability_outcomes_summary_20260223T133324Z.json`
- `docs/etl/sprints/AI-OPS-92/evidence/citizen_explainability_outcomes_markers_20260223T133324Z.txt`
- `docs/etl/sprints/AI-OPS-92/evidence/just_citizen_test_explainability_outcomes_20260223T133324Z.txt`
- `docs/etl/sprints/AI-OPS-92/evidence/just_citizen_check_explainability_outcomes_20260223T133324Z.txt`
- `docs/etl/sprints/AI-OPS-92/evidence/just_citizen_release_regression_suite_20260223T133324Z.txt`
- `docs/etl/sprints/AI-OPS-92/evidence/just_explorer_gh_pages_build_20260223T133324Z.txt`
