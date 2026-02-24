# AI-OPS-32 Closeout

Status:
- `PASS`

Date:
- 2026-02-22

Objective result:
- Declared-lane quality enforcement no longer depends on vote gate status when explicitly run in declared-only mode.

Gate adjudication:
- `G1` CLI decoupling flag shipped: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-32/evidence/declared_skip_vote_gate_tests_20260222T195036Z.txt`
- `G2` Declared `just` targets decoupled by default: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-32/evidence/quality_declared_gate_skip_vote_enforce_20260222T194957Z.txt`
- `G3` Real enforce run via `just`: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-32/evidence/quality_declared_gate_skip_vote_enforce_20260222T194957Z.json`
  - key result: `declared.gate.passed=true`, `review_pending=0`
- `G4` Tracker integrity after updates: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-32/evidence/tracker_gate_20260222T195041Z.txt` (`mismatches=0`, `waivers_active=0`, `done_zero_real=0`)

Shipped files:
- `etl/parlamentario_es/cli.py`
- `justfile`
- `tests/test_cli_quality_report.py`
- `docs/etl/sprints/AI-OPS-32/reports/declared-skip-vote-gate-20260222.md`

Next:
- Start AI-OPS-33 controllable lane: citizen evidence UX upgrades with explicit confidence/unknown semantics in static output.
