# AI-OPS-46 Kickoff

Date:
- 2026-02-22

Objective:
- Add a single strict “preset contract bundle” reporter that aggregates fixture contract, codec parity, and codec sync-state into one machine-readable artifact for local and CI triage.

Why now:
- AI-OPS-45 delivers strict checks per contract.
- We still need one canonical artifact for fast incident triage and collaborator handoff without stitching multiple JSON files manually.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_contract_bundle.js` + tests + `just` target + CI artifact upload.

Acceptance gates:
- Bundle report includes per-contract status + nested summaries and global totals (`sections_fail`, `failed_sections`, `failed_ids`).
- `--strict` fails when any sub-contract fails.
- `just citizen-test-preset-codec` includes bundle tests.
- CI uploads `citizen-preset-contract-bundle` artifact.
- Existing preset contract/parity/sync strict checks remain green.
