# AI-OPS-18 Closeout

Date: 2026-02-17  
Status: PASS

## Objective
Ship a citizen-first GH Pages webapp that turns the existing data into answers people care about, with audit links to evidence (no black box).

## What Shipped (Visible)
- GH Pages citizen app: `/citizen` (static)
- Landing entry-point on `/` explorers page
- Deterministic snapshot export + validation integrated into `just explorer-gh-pages-build`

## Gates (G1-G6)
See full adjudication: `docs/etl/sprints/AI-OPS-18/reports/gate-adjudication.md`.

| Gate | Verdict | Evidence |
|---|---|---|
| G1 Visible product | PASS | `docs/etl/sprints/AI-OPS-18/evidence/landing-link.txt`; `docs/etl/sprints/AI-OPS-18/evidence/gh-pages-publish.log` |
| G2 Evidence drill-down | PASS | `docs/etl/sprints/AI-OPS-18/reports/link-check.md`; `docs/etl/sprints/AI-OPS-18/reports/citizen-walkthrough.md` |
| G3 Honesty | PASS | `docs/etl/sprints/AI-OPS-18/evidence/citizen-validate.txt` |
| G4 Size/perf | PASS | `docs/etl/sprints/AI-OPS-18/evidence/citizen-json-size.txt` |
| G5 Strict gate/parity | PASS | `docs/etl/sprints/AI-OPS-18/evidence/tracker-gate-postrun.exit`; `docs/etl/sprints/AI-OPS-18/evidence/status-parity-postrun.txt` |
| G6 Reproducibility | PASS | `scripts/export_citizen_snapshot.py`; `scripts/validate_citizen_snapshot.py` |

## Key Artifact KPIs
- Snapshot size + stance distribution: `docs/etl/sprints/AI-OPS-18/evidence/citizen-validate.txt`
- Coverage by concern tags: `docs/etl/sprints/AI-OPS-18/exports/citizen_kpis.csv`

## How To Reproduce
Build static site (includes citizen export + validation):
```bash
just explorer-gh-pages-build
```

Publish to GH Pages branch:
```bash
just explorer-gh-pages-publish
```

## Next Sprint Trigger
- Start `AI-OPS-19` (programas/partidos declared positions slice) now that the citizen UI surface exists and can consume bounded artifacts.
