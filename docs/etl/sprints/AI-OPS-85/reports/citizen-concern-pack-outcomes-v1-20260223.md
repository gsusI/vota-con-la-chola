# Citizen Concern-Pack Outcomes v1 (AI-OPS-85)

Date:
- 2026-02-23

Goal:
- Introduce a reproducible telemetry contract for concern-pack outcomes (selection + weak-pack follow-through) without adding backend dependencies.

What shipped:
- `/citizen` concern-pack outcome telemetry in `ui/citizen/index.html`:
  - local storage lane `vclc_concern_pack_outcome_events_v1`
  - events: `pack_selected`, `pack_cleared`, `topic_open_with_pack`
  - debug APIs: `__vclcConcernPackOutcomeSummary`, `__vclcConcernPackOutcomeExport`, `__vclcConcernPackOutcomeClear`
  - status chip marker `pack_follow`
- New strict reporter:
  - `scripts/report_citizen_concern_pack_outcomes.py`
  - outputs `ok|degraded|failed` with thresholds for:
    - minimum pack selections
    - minimum weak-pack selection sessions
    - minimum weak-pack follow-through rate
    - maximum unknown-pack select share
- New fixtures:
  - `tests/fixtures/citizen_concern_pack_outcome_events_sample.jsonl`
  - `tests/fixtures/citizen_concern_pack_quality_sample.json`
- New tests:
  - `tests/test_report_citizen_concern_pack_outcomes.py`
  - `tests/test_citizen_concern_pack_outcomes_ui_contract.js`
- `just` integration:
  - `just citizen-test-concern-pack-outcomes`
  - `just citizen-report-concern-pack-outcomes`
  - `just citizen-check-concern-pack-outcomes`
  - lane added into `just citizen-release-regression-suite`

Validation:
- `just citizen-test-concern-pack-outcomes`
- `just citizen-report-concern-pack-outcomes`
- `just citizen-check-concern-pack-outcomes`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`
- `just citizen-check-release-hardening`

Strict concern-pack outcome result:
- `status=ok`
- `pack_selected_events_total=24`
- `weak_pack_selected_sessions_total=7`
- `weak_pack_followthrough_rate=1.0`
- `unknown_pack_select_share=0.083333`

Evidence:
- `docs/etl/sprints/AI-OPS-85/evidence/citizen_concern_pack_outcomes_latest.json`
- `docs/etl/sprints/AI-OPS-85/evidence/citizen_concern_pack_outcomes_summary_20260223T122520Z.json`
- `docs/etl/sprints/AI-OPS-85/evidence/just_citizen_check_concern_pack_outcomes_20260223T122520Z.txt`
- `docs/etl/sprints/AI-OPS-85/evidence/just_citizen_release_regression_suite_20260223T122520Z.txt`
- `docs/etl/sprints/AI-OPS-85/evidence/just_citizen_check_release_hardening_20260223T122520Z.txt`
