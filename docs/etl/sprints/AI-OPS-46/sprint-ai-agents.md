# AI-OPS-46 Prompt Pack

Objective:
- Consolidate citizen preset contract checks into a single strict bundle report artifact for local/CI runs.

Acceptance gates:
- New script: `scripts/report_citizen_preset_contract_bundle.js`.
- Bundle output includes:
  - contract-level status (`fixture_contract`, `codec_parity`, `codec_sync_state`)
  - global summary (`sections_total/pass/fail`, `failed_sections`, `failed_ids`)
  - nested source reports for deep triage.
- Strict mode exits non-zero when any section fails.
- Node tests cover strict pass and strict fail bundle scenarios.
- New `just` target: `citizen-report-preset-contract-bundle`.
- CI uploads artifact `citizen-preset-contract-bundle`.

Status update (2026-02-22):
- Added bundle reporter, tests, just target, and CI artifact upload.
- Preserved existing strict per-contract checks and artifacts.
- evidence:
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_contract_report_20260222T212633Z.json`
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_codec_parity_report_20260222T212633Z.json`
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_codec_sync_report_20260222T212633Z.json`
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_contract_bundle_report_20260222T212633Z.json`
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_codec_tests_20260222T212633Z.txt`
  - `docs/etl/sprints/AI-OPS-46/evidence/explorer_gh_pages_build_20260222T212633Z.txt`
  - `docs/etl/sprints/AI-OPS-46/evidence/tracker_gate_posttrackeredit_20260222T212821Z.txt`
  - `docs/etl/sprints/AI-OPS-46/evidence/citizen_preset_ci_bundle_markers_20260222T212633Z.txt`
