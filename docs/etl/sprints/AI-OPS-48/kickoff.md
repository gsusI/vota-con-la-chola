# AI-OPS-48 Kickoff

Date:
- 2026-02-22

Objective:
- Add a strict “history window” reporter that summarizes regressions over the last N bundle-history entries.

Why now:
- AI-OPS-47 persists run-by-run bundle history.
- We still need fast trend summarization for recent runs without scanning the whole JSONL manually.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_contract_bundle_history_window.js` + tests + `just` target + CI artifact upload.

Acceptance gates:
- Window report includes `window_last`, `entries_in_window`, `regressions_in_window`, and `regression_events`.
- `--strict` exits non-zero if regressions exist in the selected window.
- `just citizen-test-preset-codec` includes history-window tests.
- CI uploads artifact `citizen-preset-contract-bundle-history-window`.
- Existing strict reports remain green.
