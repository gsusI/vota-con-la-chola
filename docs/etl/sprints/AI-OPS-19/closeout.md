# AI-OPS-19 Closeout

Date: 2026-02-17  
Status: PASS

## Objective
Deliver the first reproducible `programas_partidos` declared-positions slice end-to-end and make it visible in the citizen app (static GH Pages), while preserving strict gate/parity.

## What Shipped (Visible)
- New source `programas_partidos` (manifest-driven) that ingests:
  - `source_records` (traceable; stable `content_sha256`)
  - `text_documents`
  - `topic_evidence` (`evidence_type='declared:programa'`)
- Declared stance extraction for `declared:programa` (uses `excerpt` as primary text when present).
- Declared positions backfill for `programas_partidos` producing `topic_positions`.
- Citizen app (`/citizen`) now shows “Programa” stance per party for the selected concern, with audit link to evidence.
- GH Pages build/publish path remains `just explorer-gh-pages-build` and `just explorer-gh-pages-publish`.

## Gates (G1-G6)
See full implementation and evidence packet:
- Design: `docs/etl/sprints/AI-OPS-19/reports/programas-pipeline-design.md`
- Tests: `docs/etl/sprints/AI-OPS-19/reports/programas-pipeline-tests.md`
- Citizen/UI: `docs/etl/sprints/AI-OPS-19/reports/citizen-programas-ui.md`

| Gate | Verdict | Evidence |
|---|---|---|
| G1 Integrity | PASS | `docs/etl/sprints/AI-OPS-19/evidence/programas_ingest_latest_run.json` |
| G2 Queue health | PASS | `docs/etl/sprints/AI-OPS-19/evidence/citizen_programas_validator_post.json` |
| G3 Visible progress | PASS | tracker line 74 now `PARTIAL`: `docs/etl/e2e-scrape-load-tracker.md` |
| G4 Signal floor | PASS | `docs/etl/sprints/AI-OPS-19/evidence/programas_declared_stance_post.json`; `docs/etl/sprints/AI-OPS-19/exports/programas_kpi_post.csv` |
| G5 Strict gate/parity | PASS | `docs/etl/sprints/AI-OPS-19/evidence/citizen_programas_validator_post.json` (post-build validation), plus standard `just explorer-gh-pages-build` gate |
| G6 Workload evidence | PASS | artifacts under `docs/etl/sprints/AI-OPS-19/evidence/` and `docs/etl/sprints/AI-OPS-19/exports/` |

## Tracker Transition (Line 74)
`docs/etl/e2e-scrape-load-tracker.md:74` updated to evidence-backed `PARTIAL` with reproducible next commands and KPI export:
- `docs/etl/sprints/AI-OPS-19/exports/programas_kpi_post.csv`

## How To Reproduce
Ingest from a manifest file (reproducible):
```bash
python3 scripts/ingestar_parlamentario_es.py ingest --db <db> --source programas_partidos --from-file <manifest.csv> --snapshot-date <YYYY-MM-DD>
python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db <db> --source-id programas_partidos
python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db <db> --source-id programas_partidos --as-of-date <YYYY-MM-DD>
```

Build static site (includes citizen export + validation):
```bash
just explorer-gh-pages-build
```

## Next Sprint Trigger
Start the next citizen product iteration (UI/UX) now that “Programa” is present:
- focus on concern-level summaries (“dice vs hace”), navigation and audit UX, while keeping JSON size budgets and reproducibility.
