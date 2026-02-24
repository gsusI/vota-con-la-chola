# AI-OPS-49 Kickoff

Date:
- 2026-02-22

Objective:
- Add configurable history compaction for citizen preset contract bundle history, with strict machine-readable checks and CI artifact output.

Why now:
- AI-OPS-47 added append-only bundle history.
- AI-OPS-48 added last-N regression window summary.
- We still need long-run maintenance of history size while preserving incident visibility and deterministic cadence.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_contract_bundle_history_compaction.js` + tests + `just` target + CI artifact upload.

Acceptance gates:
- Compaction report includes raw/selected/dropped counts, cadence settings, tier stats, and strict fail reasons.
- Compaction always keeps anchors (oldest/latest) and incident rows.
- `--strict` fails on invalid compaction safety conditions.
- `just citizen-test-preset-codec` includes compaction tests.
- CI uploads artifact `citizen-preset-contract-bundle-history-compaction`.
- Existing strict preset report chain remains green.
