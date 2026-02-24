# AI-OPS-44 Prompt Pack

Objective:
- Enforce source-to-published preset codec parity with deterministic JSON evidence in local and CI loops.

Acceptance gates:
- New script `scripts/report_citizen_preset_codec_parity.js` supports `--source`, `--published`, `--json-out`, `--strict`.
- Reporter fails strict mode on mismatch and reports `first_diff_line` + file hashes.
- Node tests cover strict pass and strict fail parity paths.
- `just citizen-report-preset-codec-parity` is available and strict by default.
- CI `citizen-preset-contract` job uploads parity artifact `citizen-preset-codec-parity`.
- Local controllable gates remain green.

Status update (2026-02-22):
- Added parity reporter, tests, just target, and CI artifact upload for parity JSON.
- Updated citizen preset test bundle to include parity reporter coverage.
- evidence:
  - `docs/etl/sprints/AI-OPS-44/evidence/citizen_preset_contract_report_20260222T211445Z.json`
  - `docs/etl/sprints/AI-OPS-44/evidence/citizen_preset_codec_parity_report_20260222T211445Z.json`
  - `docs/etl/sprints/AI-OPS-44/evidence/citizen_preset_codec_tests_20260222T211445Z.txt`
  - `docs/etl/sprints/AI-OPS-44/evidence/explorer_gh_pages_build_20260222T211445Z.txt`
  - `docs/etl/sprints/AI-OPS-44/evidence/tracker_gate_postdocs_20260222T211445Z.txt`
  - `docs/etl/sprints/AI-OPS-44/evidence/citizen_preset_ci_parity_markers_20260222T211445Z.txt`
