# AI-OPS-95 Closeout

Status:
- PASS

Date:
- 2026-02-23

Objective result:
- Mobile observability heartbeat retention v1 is shipped: compaction is incident-preserving and strict raw-vs-compacted window parity is enforced with dedicated lanes/tests integrated into release regression.

Gate adjudication:
- G1 Compaction lane shipped with p90-incident preservation: PASS
  - evidence: `scripts/report_citizen_mobile_observability_heartbeat_compaction.py`
  - evidence: `docs/etl/sprints/AI-OPS-95/evidence/citizen_mobile_observability_heartbeat_compaction_20260223T140552Z.json`
- G2 Compaction-window parity lane shipped: PASS
  - evidence: `scripts/report_citizen_mobile_observability_heartbeat_compaction_window.py`
  - evidence: `docs/etl/sprints/AI-OPS-95/evidence/citizen_mobile_observability_heartbeat_compaction_window_20260223T140552Z.json`
- G3 Deterministic tests and lane wiring shipped: PASS
  - evidence: `tests/test_report_citizen_mobile_observability_heartbeat_compaction.py`
  - evidence: `tests/test_report_citizen_mobile_observability_heartbeat_compaction_window.py`
  - evidence: `justfile`
- G4 Strict compaction/parity checks pass: PASS
  - evidence: `docs/etl/sprints/AI-OPS-95/evidence/just_citizen_check_mobile_observability_heartbeat_compact_20260223T140552Z.txt`
  - evidence: `docs/etl/sprints/AI-OPS-95/evidence/just_citizen_check_mobile_observability_heartbeat_compact_window_20260223T140552Z.txt`
- G5 Release regression suite + GH Pages build remain green: PASS
  - evidence: `docs/etl/sprints/AI-OPS-95/evidence/just_citizen_release_regression_suite_20260223T140552Z.txt`
  - evidence: `docs/etl/sprints/AI-OPS-95/evidence/just_explorer_gh_pages_build_20260223T140552Z.txt`

Shipped files:
- `scripts/report_citizen_mobile_observability_heartbeat_compaction.py`
- `scripts/report_citizen_mobile_observability_heartbeat_compaction_window.py`
- `tests/test_report_citizen_mobile_observability_heartbeat_compaction.py`
- `tests/test_report_citizen_mobile_observability_heartbeat_compaction_window.py`
- `justfile`
- `docs/etl/sprints/AI-OPS-95/sprint-ai-agents.md`
- `docs/etl/sprints/AI-OPS-95/kickoff.md`
- `docs/etl/sprints/AI-OPS-95/reports/citizen-mobile-observability-heartbeat-retention-v1-20260223.md`
- `docs/etl/sprints/AI-OPS-95/closeout.md`

Next:
- Move to AI-OPS-96: Tailwind+MD3 visual drift digest v1 (source/published style parity contract with strict drift checks).
