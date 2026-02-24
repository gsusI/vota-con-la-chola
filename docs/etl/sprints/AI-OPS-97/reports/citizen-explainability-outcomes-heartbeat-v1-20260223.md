# Citizen Explainability Outcomes Heartbeat v1 (AI-OPS-97)

Date:
- 2026-02-23

Goal:
- Add an append-only trend lane and strict last-N checks for explainability adoption outcomes in `/citizen`.

What shipped:
- New heartbeat reporter:
  - `scripts/report_citizen_explainability_outcomes_heartbeat.py`
  - reads digest (`report_citizen_explainability_outcomes.py`) and appends deduped rows into JSONL
  - captures `status`, interactions (`glossary/help_copy`), adoption metrics, thresholds, `contract_complete`, and reason fields
- New window reporter:
  - `scripts/report_citizen_explainability_outcomes_heartbeat_window.py`
  - evaluates trailing window thresholds for:
    - `failed` count/rate
    - `degraded` count/rate
    - `contract_incomplete` count/rate
  - enforces latest-row checks (`latest_not_failed_ok`, `latest_contract_complete_ok`)
- New tests:
  - `tests/test_report_citizen_explainability_outcomes_heartbeat.py`
  - `tests/test_report_citizen_explainability_outcomes_heartbeat_window.py`
- `just` wiring:
  - new vars: `citizen_explainability_outcome_heartbeat_*`
  - new lanes:
    - `just citizen-test-explainability-outcomes-heartbeat`
    - `just citizen-report-explainability-outcomes-heartbeat`
    - `just citizen-check-explainability-outcomes-heartbeat`
    - `just citizen-report-explainability-outcomes-heartbeat-window`
    - `just citizen-check-explainability-outcomes-heartbeat-window`
  - heartbeat test lane added to `just citizen-release-regression-suite`

Validation:
- `python3 -m py_compile scripts/report_citizen_explainability_outcomes_heartbeat.py scripts/report_citizen_explainability_outcomes_heartbeat_window.py tests/test_report_citizen_explainability_outcomes_heartbeat.py tests/test_report_citizen_explainability_outcomes_heartbeat_window.py`
- `just citizen-test-explainability-outcomes-heartbeat`
- `just citizen-check-explainability-outcomes-heartbeat`
- `just citizen-check-explainability-outcomes-heartbeat-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict run result:
- Heartbeat check: PASS (`status=ok`, `history_size_after=1`, `duplicate_detected=false`, `strict_fail_reasons=[]`)
- Window check: PASS (`status=ok`, `entries_in_window=1`, `latest_contract_complete_ok=true`, `strict_fail_reasons=[]`)

Evidence:
- `docs/etl/sprints/AI-OPS-97/evidence/citizen_explainability_outcomes_heartbeat_latest.json`
- `docs/etl/sprints/AI-OPS-97/evidence/citizen_explainability_outcomes_heartbeat_window_latest.json`
- `docs/etl/sprints/AI-OPS-97/evidence/citizen_explainability_outcomes_heartbeat_20260223T142226Z.json`
- `docs/etl/sprints/AI-OPS-97/evidence/citizen_explainability_outcomes_heartbeat_window_20260223T142226Z.json`
- `docs/etl/sprints/AI-OPS-97/evidence/just_citizen_test_explainability_outcomes_heartbeat_20260223T142226Z.txt`
- `docs/etl/sprints/AI-OPS-97/evidence/just_citizen_check_explainability_outcomes_heartbeat_20260223T142226Z.txt`
- `docs/etl/sprints/AI-OPS-97/evidence/just_citizen_check_explainability_outcomes_heartbeat_window_20260223T142226Z.txt`
- `docs/etl/sprints/AI-OPS-97/evidence/just_citizen_release_regression_suite_20260223T142226Z.txt`
- `docs/etl/sprints/AI-OPS-97/evidence/just_explorer_gh_pages_build_20260223T142226Z.txt`
