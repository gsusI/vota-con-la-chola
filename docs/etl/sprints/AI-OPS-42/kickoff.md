# AI-OPS-42 Kickoff

Date:
- 2026-02-22

Objective:
- Add a fast preset-fixture contract drift reporter with machine-readable counts and failed IDs for QA triage.

Why now:
- AI-OPS-41 centralized read/share behavior into fixture schema `v2`.
- We still need a one-command status report that highlights exactly which fixture rows drifted.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_fixture_contract.js` + `just` target + tests.

Acceptance gates:
- Reporter emits JSON with totals by `hash_cases`/`share_cases` and `failed_ids`.
- `--strict` exits non-zero on drift.
- Node tests cover strict pass and strict fail paths.
- `just citizen-test-preset-codec`, `just explorer-gh-pages-build`, and `just etl-tracker-gate` pass with evidence.
