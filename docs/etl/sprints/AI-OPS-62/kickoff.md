# AI-OPS-62 Kickoff

Date:
- 2026-02-22

Objective:
- Enforce the Senado initiative actionable-tail queue contract in CI with deterministic fail/pass checks, so regressions are caught before merge.

Primary lane (controllable):
- CI workflow hardening (`.github/workflows/etl-tracker-gate.yml`) + existing actionable export contract.

Acceptance gates:
- New workflow job `initdoc-actionable-tail-contract` in `etl-tracker-gate.yml`.
- Job covers:
  - unit tests for `export_missing_initiative_doc_urls.py`
  - deterministic fixture DB build
  - strict-empty failure path (expect exit `4` with actionable row)
  - strict-empty success path (expect exit `0` after converting row to redundant global)
  - artifact upload with logs/CSVs
- Docs updated to point operators to CI contract.

DoD:
- Local evidence reproduces fail/pass contract.
- Sprint docs + tracker + sprint index updated.
