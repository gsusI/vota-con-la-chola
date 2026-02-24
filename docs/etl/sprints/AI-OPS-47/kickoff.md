# AI-OPS-47 Kickoff

Date:
- 2026-02-22

Objective:
- Add a strict contract-bundle history reporter that appends run snapshots and flags regressions against the previous entry.

Why now:
- AI-OPS-46 provides a one-file bundle artifact per run.
- We still need deterministic trend tracking (`history_size`, regression reasons) to spot regressions early and simplify handoffs.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_contract_bundle_history.js` + tests + `just` target + CI history artifact upload.

Acceptance gates:
- History report outputs `history_size_before/after`, `regression_detected`, and `regression_reasons`.
- `--strict` exits non-zero when a regression is detected.
- `just citizen-test-preset-codec` includes history reporter tests.
- CI uploads artifact `citizen-preset-contract-bundle-history`.
- Existing strict contract/parity/sync/bundle checks remain green.
