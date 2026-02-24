# AI-OPS-63 Kickoff

Date:
- 2026-02-22

Objective:
- Add a machine-readable actionable-tail contract reporter for initiative docs and enforce it in CI alongside existing CSV strict-empty checks.

Primary lane (controllable):
- Initiative-doc queue contract hardening (reporting + CI + just/docs).

Acceptance gates:
- New script `scripts/report_initdoc_actionable_tail_contract.py` with strict mode.
- New tests in `tests/test_report_initdoc_actionable_tail_contract.py`.
- New just targets:
  - `just parl-report-initdoc-actionable-tail-contract`
  - `just parl-check-initdoc-actionable-tail-contract`
- CI job `initdoc-actionable-tail-contract` runs strict fail/pass checks for the new reporter too.
- Real DB strict run passes with actionable queue empty.

DoD:
- Tests + py_compile pass.
- Real DB evidence captured.
- Docs/tracker/sprint index updated.
