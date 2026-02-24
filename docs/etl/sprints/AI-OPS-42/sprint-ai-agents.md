# AI-OPS-42 Prompt Pack

Objective:
- Provide a deterministic CLI reporter for citizen preset fixture drift that supports rapid human/subagent triage.

Acceptance gates:
- New script: `scripts/report_citizen_preset_fixture_contract.js`.
- Reporter outputs machine-readable summary (`hash_cases_*`, `share_cases_*`, `failed_ids`).
- `--strict` fails on drift.
- Node tests cover canonical pass + forced drift fail.
- Build + tracker gates remain green.

Status update (2026-02-22):
- Added contract reporter with strict mode, JSON stdout, and optional `--json-out` export.
- Added Node tests for strict pass and strict fail paths.
- Added `just citizen-report-preset-contract` and expanded `just citizen-test-preset-codec` to include reporter tests.
- evidence:
  - `docs/etl/sprints/AI-OPS-42/evidence/citizen_preset_contract_report_20260222T210553Z.json`
  - `docs/etl/sprints/AI-OPS-42/evidence/citizen_preset_contract_markers_20260222T210553Z.txt`
  - `docs/etl/sprints/AI-OPS-42/evidence/citizen_preset_codec_tests_20260222T210553Z.txt`
  - `docs/etl/sprints/AI-OPS-42/evidence/explorer_gh_pages_build_20260222T210553Z.txt`
  - `docs/etl/sprints/AI-OPS-42/evidence/tracker_gate_posttrackeredit_20260222T210719Z.txt`
