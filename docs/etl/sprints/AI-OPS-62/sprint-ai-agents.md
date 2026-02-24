# AI-OPS-62 Prompt Pack

Objective:
- Add a deterministic CI lane that validates Senado actionable-tail queue semantics (`--only-actionable-missing` + `--strict-empty`) end-to-end.

Acceptance gates:
- `.github/workflows/etl-tracker-gate.yml` includes job `initdoc-actionable-tail-contract`.
- Job steps:
  - `python3 -m unittest tests.test_export_missing_initiative_doc_urls -q`
  - create synthetic SQLite fixture with actionable + redundant Senate rows
  - run strict-empty and assert non-empty exit (`4`)
  - mutate fixture to redundant-only and assert strict-empty pass (`0`)
  - upload artifacts (`csv` + logs)
- `docs/etl/README.md` documents this CI lane.
- Tracker includes explicit operational update for AI-OPS-62.

Status update (2026-02-22):
- Implemented and validated locally with reproducible evidence.
