# Citizen Trust-Action Nudges Heartbeat v1 (AI-OPS-101)

Date:
- 2026-02-23

Goal:
- Add an append-only observability lane for trust-action nudges so clickthrough drift is visible in strict last-N checks.

What shipped:
- New heartbeat reporter:
  - `scripts/report_citizen_trust_action_nudges_heartbeat.py`
  - appends deduped JSONL rows from trust-action nudges digest.
  - preserves key threshold/check context per run:
    - `nudge_clickthrough_session_rate`
    - `nudge_clickthrough_event_rate`
    - `contract_complete`
    - strict failure/degraded reasons.
- New window reporter:
  - `scripts/report_citizen_trust_action_nudges_heartbeat_window.py`
  - evaluates strict `last N` thresholds for:
    - status (`failed`, `degraded`)
    - completeness (`contract_incomplete`)
    - threshold violations (`nudge_clickthrough_meets_minimum`)
  - enforces latest-row checks (`latest_not_failed_ok`, `latest_contract_complete_ok`, `latest_thresholds_ok`).
- New tests:
  - `tests/test_report_citizen_trust_action_nudges_heartbeat.py`
  - `tests/test_report_citizen_trust_action_nudges_heartbeat_window.py`
- `just` wiring:
  - new vars: `citizen_trust_action_nudge_heartbeat_*`
  - new lane:
    - `just citizen-test-trust-action-nudges-heartbeat`
  - new lanes:
    - `just citizen-report-trust-action-nudges-heartbeat`
    - `just citizen-check-trust-action-nudges-heartbeat`
    - `just citizen-report-trust-action-nudges-heartbeat-window`
    - `just citizen-check-trust-action-nudges-heartbeat-window`
  - test lane added to `just citizen-release-regression-suite`

Validation:
- `python3 -m py_compile scripts/report_citizen_trust_action_nudges_heartbeat.py scripts/report_citizen_trust_action_nudges_heartbeat_window.py`
- `just citizen-test-trust-action-nudges-heartbeat`
- `just citizen-check-trust-action-nudges-heartbeat`
- `just citizen-check-trust-action-nudges-heartbeat-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict run result (`20260223T150803Z`):
- Heartbeat check: PASS (`status=ok`, `history_size_after=1`, `duplicate_detected=true`, `strict_fail_reasons=[]`)
- Window check: PASS (`status=ok`, `entries_in_window=1`, `failed_in_window=0`, `degraded_in_window=0`, `contract_incomplete_in_window=0`, `nudge_clickthrough_violations_in_window=0`, `strict_fail_reasons=[]`)

Evidence:
- `docs/etl/sprints/AI-OPS-101/evidence/citizen_trust_action_nudges_heartbeat_latest.json`
- `docs/etl/sprints/AI-OPS-101/evidence/citizen_trust_action_nudges_heartbeat_window_latest.json`
- `docs/etl/sprints/AI-OPS-101/evidence/citizen_trust_action_nudges_heartbeat_20260223T150803Z.json`
- `docs/etl/sprints/AI-OPS-101/evidence/citizen_trust_action_nudges_heartbeat_window_20260223T150803Z.json`
- `docs/etl/sprints/AI-OPS-101/evidence/citizen_trust_action_nudges_heartbeat_20260223T150803Z.jsonl`
- `docs/etl/sprints/AI-OPS-101/evidence/just_citizen_test_trust_action_nudges_heartbeat_20260223T150803Z.txt`
- `docs/etl/sprints/AI-OPS-101/evidence/just_citizen_check_trust_action_nudges_heartbeat_20260223T150803Z.txt`
- `docs/etl/sprints/AI-OPS-101/evidence/just_citizen_check_trust_action_nudges_heartbeat_window_20260223T150803Z.txt`
- `docs/etl/sprints/AI-OPS-101/evidence/just_citizen_release_regression_suite_20260223T150803Z.txt`
- `docs/etl/sprints/AI-OPS-101/evidence/just_explorer_gh_pages_build_20260223T150803Z.txt`
