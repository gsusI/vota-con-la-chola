# AI-OPS-20 Kickoff

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

Status:
- `DONE`

## Single Sprint Objective
- Ship a citizen-first GH Pages webapp iteration (Citizen Dashboard v3) that supports multi-concern synthesis + shareable URLs + method toggle while preserving auditability, honesty, and bounded static artifacts.

Scope lock:
- `docs/etl/sprints/AI-OPS-20/reports/scope-lock.md`

## Baseline (current state)
- Citizen app (today):
  - Single concern selection via `?concern=<id>` + optional `?topic_id=<n>`.
  - Party focus is not encoded in URL (not shareable).
  - No multi-concern dashboard/persistence.
- Canonical snapshot artifact:
  - `docs/gh-pages/citizen/data/citizen.json`

## In-Scope Surfaces
- UI:
  - `ui/citizen/index.html`
  - GH Pages build output: `docs/gh-pages/citizen/`
- Export/build:
  - `scripts/export_citizen_snapshot.py`
  - `scripts/validate_citizen_snapshot.py`
  - `justfile` (`explorer-gh-pages-build`)
- Docs/evidence:
  - `docs/etl/sprints/AI-OPS-20/` (this sprint folder)

## Non-Goals (explicit)
- No new upstream connectors.
- No backend services beyond static GH Pages.
- No opaque "alignment ranking" or ML personalization.

## Must-Pass Gates (AI-OPS-20)
- `G1 Visible product delta`: multi-concern dashboard (>=2 concerns) + shareable URLs restore view state.
- `G2 Auditability`: every stance/summary view has audit links; links resolve on GH Pages build.
- `G3 Honesty`: method labels accurate; `no_signal/unclear` explicit; coverage rules visible.
- `G4 Static budgets`: each citizen artifact `<= 5MB`; mobile QA acceptable.
- `G5 Reproducibility`: deterministic multi-method artifacts + validator + tests updated.
- `G6 Strict gate/parity`: strict tracker gate exit `0` and status parity `overall_match=true`.

## Execution Plan (lane packing)
- `HI` setup wave: design + contract + implementation setup (Tasks `1-8` in prompt pack)
- `FAST` throughput wave: evidence generation + validation + QA (Tasks `9-20`)
- `HI` closeout wave: reconciliation + gate adjudication + verdict (Tasks `21-24`)
