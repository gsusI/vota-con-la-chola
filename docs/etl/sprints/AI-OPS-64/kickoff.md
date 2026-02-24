# AI-OPS-64 Kickoff

Date:
- 2026-02-22

Objective:
- Add a compact actionable-tail digest contract (`ok|degraded|failed`) on top of the initiative-doc JSON contract and enforce strict fail/pass checks in CI.

Primary lane (controllable):
- Initiative-doc alerting surface hardening (digest script + tests + just + CI + docs).

Acceptance gates:
- New script `scripts/report_initdoc_actionable_tail_digest.py` with strict mode.
- New tests in `tests/test_report_initdoc_actionable_tail_digest.py`.
- New just targets:
  - `just parl-report-initdoc-actionable-tail-digest`
  - `just parl-check-initdoc-actionable-tail-digest`
- CI job `initdoc-actionable-tail-contract` validates digest strict fail/pass in fixture lane.
- Real DB strict run passes with digest `status=ok`.

DoD:
- Tests + py_compile pass.
- Real DB evidence captured.
- Docs/tracker/sprint index updated.
