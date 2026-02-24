# Citizen Coherence Drilldown Observability v1 (AI-OPS-99)

Date:
- 2026-02-23

Goal:
- Add an append-only observability lane for coherence deep-link outcomes (`/citizen` drilldown links replayed in `/explorer-temas`) with strict last-N checks.

What shipped:
- New outcomes digest reporter:
  - `scripts/report_citizen_coherence_drilldown_outcomes.py`
  - computes telemetry + contract health for coherence drilldown links and replay outcomes:
    - click and replay totals
    - replay success/failure rates
    - contract-complete click rate
    - strict checks (`telemetry`, minima, threshold compliance, `contract_complete`)
- New heartbeat reporter:
  - `scripts/report_citizen_coherence_drilldown_outcomes_heartbeat.py`
  - appends deduped JSONL rows from the digest and preserves threshold/check context per run.
- New window reporter:
  - `scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_window.py`
  - evaluates strict `last N` thresholds for:
    - status (`failed`, `degraded`)
    - completeness (`contract_incomplete`)
    - threshold violations (`replay_success_rate`, `contract_complete_click_rate`, `replay_failure_rate`)
  - enforces latest-row checks (`latest_not_failed_ok`, `latest_contract_complete_ok`, `latest_thresholds_ok`).
- New deterministic fixture:
  - `tests/fixtures/citizen_coherence_drilldown_events_sample.jsonl`
- New tests:
  - `tests/test_report_citizen_coherence_drilldown_outcomes.py`
  - `tests/test_report_citizen_coherence_drilldown_outcomes_heartbeat.py`
  - `tests/test_report_citizen_coherence_drilldown_outcomes_heartbeat_window.py`
- `just` wiring:
  - new vars: `citizen_coherence_outcome_*`
  - new lane:
    - `just citizen-test-coherence-drilldown-outcomes`
  - new lanes:
    - `just citizen-report-coherence-drilldown-outcomes`
    - `just citizen-check-coherence-drilldown-outcomes`
    - `just citizen-report-coherence-drilldown-outcomes-heartbeat`
    - `just citizen-check-coherence-drilldown-outcomes-heartbeat`
    - `just citizen-report-coherence-drilldown-outcomes-heartbeat-window`
    - `just citizen-check-coherence-drilldown-outcomes-heartbeat-window`
  - test lane added to `just citizen-release-regression-suite`

Validation:
- `python3 -m py_compile scripts/report_citizen_coherence_drilldown_outcomes.py scripts/report_citizen_coherence_drilldown_outcomes_heartbeat.py scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_window.py tests/test_report_citizen_coherence_drilldown_outcomes.py tests/test_report_citizen_coherence_drilldown_outcomes_heartbeat.py tests/test_report_citizen_coherence_drilldown_outcomes_heartbeat_window.py`
- `just citizen-test-coherence-drilldown-outcomes`
- `just citizen-check-coherence-drilldown-outcomes`
- `just citizen-check-coherence-drilldown-outcomes-heartbeat`
- `just citizen-check-coherence-drilldown-outcomes-heartbeat-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict run result (`20260223T144400Z`):
- Outcomes check: PASS (`status=ok`, `drilldown_click_events_total=10`, `replay_attempt_events_total=10`, `replay_success_rate=0.9`, `contract_complete_click_rate=0.9`)
- Heartbeat check: PASS (`status=ok`, `history_size_after=1`, `strict_fail_reasons=[]`)
- Window check: PASS (`status=ok`, `entries_in_window=1`, `contract_incomplete_in_window=0`, violation counters all `0`, `strict_fail_reasons=[]`)

Evidence:
- `docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_latest.json`
- `docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_heartbeat_latest.json`
- `docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_heartbeat_window_latest.json`
- `docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_20260223T144400Z.json`
- `docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_heartbeat_20260223T144400Z.json`
- `docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_heartbeat_window_20260223T144400Z.json`
- `docs/etl/sprints/AI-OPS-99/evidence/just_citizen_test_coherence_drilldown_outcomes_20260223T144400Z.txt`
- `docs/etl/sprints/AI-OPS-99/evidence/just_citizen_check_coherence_drilldown_outcomes_20260223T144400Z.txt`
- `docs/etl/sprints/AI-OPS-99/evidence/just_citizen_check_coherence_drilldown_outcomes_heartbeat_20260223T144400Z.txt`
- `docs/etl/sprints/AI-OPS-99/evidence/just_citizen_check_coherence_drilldown_outcomes_heartbeat_window_20260223T144400Z.txt`
- `docs/etl/sprints/AI-OPS-99/evidence/just_citizen_release_regression_suite_20260223T144400Z.txt`
- `docs/etl/sprints/AI-OPS-99/evidence/just_explorer_gh_pages_build_20260223T144400Z.txt`
