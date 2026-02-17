# AI-OPS-17 Closeout

Date: 2026-02-17  
Status: PASS

## Objective
Ship a citizen-first GH Pages UI iteration that answers the fastest question:
- "Que hizo cada partido sobre esta preocupacion?"

Without losing auditability (always link to evidence) and while keeping artifacts bounded and reproducible.

## What Shipped (Visible)
- Citizen UI v2 (static):
  - concern-level party summaries when no item is selected
  - party focus drill-down ("Ver top items") with inline stance chips in the items list
  - honest method labeling (`votes` vs `combined`)
- Citizen snapshot export improvements:
  - deterministic topic tagging `topics[].concern_ids` (optional v2)
  - `meta.methods_available` (optional v2)
  - bounded selection via `--max-items-per-concern`
- Link-check + strict gate/parity evidence captured under this sprint folder.

## Gates (G1-G6)
See full adjudication: `docs/etl/sprints/AI-OPS-17/reports/gate-adjudication.md`.

| Gate | Verdict | Evidence |
|---|---|---|
| G1 Visible UX (Concern-Level Summary) | PASS | `docs/etl/sprints/AI-OPS-17/reports/citizen-ui-v2.md`; `docs/etl/sprints/AI-OPS-17/reports/citizen-walkthrough.md` |
| G2 Audit Drill-Down | PASS | `docs/etl/sprints/AI-OPS-17/reports/link-check.md` |
| G3 Honesty | PASS | `ui/citizen/index.html`; `docs/etl/sprints/AI-OPS-17/evidence/gh-pages-build.log` |
| G4 Static Budget | PASS | `docs/etl/sprints/AI-OPS-17/evidence/citizen-json-size.txt` |
| G5 Reproducibility | PASS | `docs/etl/sprints/AI-OPS-17/evidence/gh-pages-build.log` |
| G6 Strict Gate/Parity | PASS | `docs/etl/sprints/AI-OPS-17/evidence/tracker-gate-postrun.exit`; `docs/etl/sprints/AI-OPS-17/evidence/status-parity-postrun.txt` |

## How To Reproduce
Build static site (includes citizen export + strict validation):
```bash
just explorer-gh-pages-build
```

Strict gate (tracker):
```bash
just etl-tracker-gate
```

## Next Sprint Trigger
- Improve citizen onboarding and concern taxonomy UX while keeping bounded artifacts and audit links.
