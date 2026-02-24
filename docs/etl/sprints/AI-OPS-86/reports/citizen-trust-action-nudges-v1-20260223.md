# Citizen Trust-Action Nudges v1 (AI-OPS-86)

Date:
- 2026-02-23

Goal:
- Introduce deterministic trust-to-action nudges that explicitly tell the user the next best evidence click, with strict telemetry gates.

What shipped:
- Trust-action nudge helper contract in `ui/citizen/evidence_trust_panel.js`:
  - new function `buildTrustActionNudge(input)`
  - deterministic candidate ranking (trust gap + unknown + coverage + tie-break by label)
  - stable nudge payload (`nudge_id`, reason, link target, message)
- `/citizen` integration in `ui/citizen/index.html`:
  - nudge rendering helper (`renderTrustActionNudge`)
  - click wiring (`wireTrustActionNudgeLinks`)
  - nudge surfaced in dashboard/concern/topic compare summaries (`trust_next_evidence` marker)
  - telemetry lane: `vclc_trust_action_nudge_events_v1`
  - debug APIs:
    - `__vclcTrustActionNudgeSummary`
    - `__vclcTrustActionNudgeExport`
    - `__vclcTrustActionNudgeClear`
  - status chip `nudge_ctr`
- Strict KPI reporter:
  - `scripts/report_citizen_trust_action_nudges.py`
  - checks minimum shown volume/sessions + minimum nudge clickthrough rate
- Fixtures:
  - `tests/fixtures/citizen_trust_action_nudge_events_sample.jsonl`
- Tests:
  - `tests/test_citizen_trust_action_nudges.js`
  - `tests/test_citizen_trust_action_nudges_ui_contract.js`
  - `tests/test_report_citizen_trust_action_nudges.py`
- `just` integration:
  - `just citizen-test-trust-action-nudges`
  - `just citizen-report-trust-action-nudges`
  - `just citizen-check-trust-action-nudges`
  - lane added to `just citizen-release-regression-suite`

Validation:
- `just citizen-test-trust-action-nudges`
- `just citizen-report-trust-action-nudges`
- `just citizen-check-trust-action-nudges`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`
- `just citizen-check-release-hardening`

Strict trust-action KPI result:
- `status=ok`
- `nudge_shown_events_total=8`
- `nudge_shown_sessions_total=8`
- `nudge_clicked_sessions_total=5`
- `nudge_clickthrough_session_rate=0.625`

Evidence:
- `docs/etl/sprints/AI-OPS-86/evidence/citizen_trust_action_nudges_latest.json`
- `docs/etl/sprints/AI-OPS-86/evidence/citizen_trust_action_nudges_summary_20260223T123736Z.json`
- `docs/etl/sprints/AI-OPS-86/evidence/citizen_trust_action_nudges_markers_20260223T123736Z.txt`
- `docs/etl/sprints/AI-OPS-86/evidence/just_citizen_check_trust_action_nudges_20260223T123736Z.txt`
- `docs/etl/sprints/AI-OPS-86/evidence/just_citizen_release_regression_suite_20260223T123736Z.txt`
- `docs/etl/sprints/AI-OPS-86/evidence/just_citizen_check_release_hardening_20260223T123736Z.txt`
