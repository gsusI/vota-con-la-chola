# Citizen Concern-Pack Outcomes Heartbeat v1 (AI-OPS-100)

Date:
- 2026-02-23

Goal:
- Add an append-only observability lane for concern-pack outcomes so weak-pack followthrough and unknown-share drift are visible in strict last-N checks.

What shipped:
- New heartbeat reporter:
  - `scripts/report_citizen_concern_pack_outcomes_heartbeat.py`
  - appends deduped JSONL rows from concern-pack outcomes digest.
  - preserves key threshold/check context per run:
    - `weak_pack_followthrough_rate`
    - `unknown_pack_select_share`
    - `contract_complete`
    - strict failure/degraded reasons.
- New window reporter:
  - `scripts/report_citizen_concern_pack_outcomes_heartbeat_window.py`
  - evaluates strict `last N` thresholds for:
    - status (`failed`, `degraded`)
    - completeness (`contract_incomplete`)
    - threshold violations (`weak_pack_followthrough_rate_meets_minimum`, `unknown_pack_select_share_within_threshold`)
  - enforces latest-row checks (`latest_not_failed_ok`, `latest_contract_complete_ok`, `latest_thresholds_ok`).
- New tests:
  - `tests/test_report_citizen_concern_pack_outcomes_heartbeat.py`
  - `tests/test_report_citizen_concern_pack_outcomes_heartbeat_window.py`
- `just` wiring:
  - new vars: `citizen_pack_outcome_heartbeat_*`
  - new lane:
    - `just citizen-test-concern-pack-outcomes-heartbeat`
  - new lanes:
    - `just citizen-report-concern-pack-outcomes-heartbeat`
    - `just citizen-check-concern-pack-outcomes-heartbeat`
    - `just citizen-report-concern-pack-outcomes-heartbeat-window`
    - `just citizen-check-concern-pack-outcomes-heartbeat-window`
  - test lane added to `just citizen-release-regression-suite`

Validation:
- `python3 -m py_compile scripts/report_citizen_concern_pack_outcomes_heartbeat.py scripts/report_citizen_concern_pack_outcomes_heartbeat_window.py`
- `just citizen-test-concern-pack-outcomes-heartbeat`
- `just citizen-check-concern-pack-outcomes-heartbeat`
- `just citizen-check-concern-pack-outcomes-heartbeat-window`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Strict run result (`20260223T145733Z`):
- Heartbeat check: PASS (`status=ok`, `history_size_after=1`, `duplicate_detected=true`, `strict_fail_reasons=[]`)
- Window check: PASS (`status=ok`, `entries_in_window=1`, `failed_in_window=0`, `degraded_in_window=0`, `contract_incomplete_in_window=0`, `weak_pack_followthrough_violations_in_window=0`, `unknown_pack_select_share_violations_in_window=0`, `strict_fail_reasons=[]`)

Evidence:
- `docs/etl/sprints/AI-OPS-100/evidence/citizen_concern_pack_outcomes_heartbeat_latest.json`
- `docs/etl/sprints/AI-OPS-100/evidence/citizen_concern_pack_outcomes_heartbeat_window_latest.json`
- `docs/etl/sprints/AI-OPS-100/evidence/citizen_concern_pack_outcomes_heartbeat_20260223T145733Z.json`
- `docs/etl/sprints/AI-OPS-100/evidence/citizen_concern_pack_outcomes_heartbeat_window_20260223T145733Z.json`
- `docs/etl/sprints/AI-OPS-100/evidence/citizen_concern_pack_outcomes_heartbeat_20260223T145733Z.jsonl`
- `docs/etl/sprints/AI-OPS-100/evidence/just_citizen_test_concern_pack_outcomes_heartbeat_20260223T145733Z.txt`
- `docs/etl/sprints/AI-OPS-100/evidence/just_citizen_check_concern_pack_outcomes_heartbeat_20260223T145733Z.txt`
- `docs/etl/sprints/AI-OPS-100/evidence/just_citizen_check_concern_pack_outcomes_heartbeat_window_20260223T145733Z.txt`
- `docs/etl/sprints/AI-OPS-100/evidence/just_citizen_release_regression_suite_20260223T145733Z.txt`
- `docs/etl/sprints/AI-OPS-100/evidence/just_explorer_gh_pages_build_20260223T145733Z.txt`
