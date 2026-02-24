# AI-OPS-43 Prompt Pack

Objective:
- Make citizen preset contract enforcement first-class in CI with artifacted JSON evidence.

Acceptance gates:
- Add workflow job `citizen-preset-contract` in `.github/workflows/etl-tracker-gate.yml`.
- Job must run:
  - Node preset tests
  - strict `report_citizen_preset_fixture_contract.js`
- Job uploads `citizen_preset_contract_ci.json` via `actions/upload-artifact@v4`.
- Local controllable gates remain green.

Status update (2026-02-22):
- Added CI job with Node setup, preset tests, strict reporter execution, and artifact upload.
- Preserved existing tracker/vote/HF jobs.
- evidence:
  - `docs/etl/sprints/AI-OPS-43/evidence/citizen_preset_ci_workflow_markers_20260222T211006Z.txt`
  - `docs/etl/sprints/AI-OPS-43/evidence/citizen_preset_contract_report_20260222T211006Z.json`
  - `docs/etl/sprints/AI-OPS-43/evidence/citizen_preset_codec_tests_20260222T211006Z.txt`
  - `docs/etl/sprints/AI-OPS-43/evidence/explorer_gh_pages_build_20260222T211006Z.txt`
  - `docs/etl/sprints/AI-OPS-43/evidence/tracker_gate_posttrackeredit_20260222T211006Z.txt`
